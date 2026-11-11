"""Transport-level protections: API key, body-size cap, rate limit."""

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def check_api_key(provided: str | None, expected: str) -> bool:
    # Constant-time comparison so response timing doesn't leak the key prefix.
    return hmac.compare_digest((provided or "").encode(), expected.encode())


class BodySizeLimit:
    """Reject request bodies over `max_bytes`, including chunked uploads without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        for name, value in scope.get("headers", []):
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                return await _send_413(send)

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _TooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await _send_413(send)


class _TooLarge(Exception):
    pass


async def _send_413(send: Send) -> None:
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"detail":"request too large"}'})


class RateLimiter:
    """Sliding-window limiter keyed by client. In-memory: fine for a single-instance prototype.

    Runs BEFORE the API-key check, so key guessing is rate-limited too. The client table is
    bounded (MAX_CLIENTS) so many distinct source addresses can't grow memory without limit.
    """

    MAX_CLIENTS = 10_000

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        if len(self._hits) > self.MAX_CLIENTS:
            # First drop clients idle for a minute; if still over the cap (a burst from many
            # addresses), drop the least recently seen. Bounded memory beats perfect fairness here.
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                del self._hits[k]
            if len(self._hits) > self.MAX_CLIENTS:
                by_age = sorted(self._hits, key=lambda k: self._hits[k][-1] if self._hits[k] else 0)
                for k in by_age[: len(self._hits) - self.MAX_CLIENTS]:
                    del self._hits[k]
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.per_minute:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate limit exceeded")
        hits.append(now)
