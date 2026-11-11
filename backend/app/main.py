"""MailLens backend: stateless, no database, no outbound network calls."""

import json
import re
import logging
import os
import uuid
from pathlib import Path
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import engine
from .config import Settings, load_settings
from .schemas import AnalyzeRequest, AnalyzeResponse
from .security import BodySizeLimit, RateLimiter, check_api_key

log = logging.getLogger("maillens")
DEV = os.environ.get("MAILLENS_DEV_PROBE") == "1"
# Synthetic demo-mailbox Message-IDs only (see demo/build_seed.py); real mail never matches.
_DEMO_ID = re.compile(r"^<([a-z0-9]{1,8})\.maillens-demo@mail\.example>$")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MailLens", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    limiter = RateLimiter(settings.rate_limit_per_minute)

    def require_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        limiter.check(request)
        if not check_api_key(x_api_key, settings.api_key):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where validation failed, never the offending (attacker-controlled) value.
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()][:10]
        return JSONResponse(status_code=422, content={"detail": "invalid request", "fields": fields})

    @app.exception_handler(Exception)
    async def on_error(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error type=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_key)])
    def analyze(req: AnalyzeRequest, x_maillens_timing: str | None = Header(default=None)) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex[:12]
        resp, decision = engine.analyze(req, request_id)
        # Log decisions only, never message content or addresses.
        demo = ""
        if DEV and (m := _DEMO_ID.match(req.message.message_id or "")):
            demo = f" demo={m.group(1)}"
        if DEV and x_maillens_timing:  # client-supplied: keep only a safe character set
            demo += " client_ms=" + re.sub(r"[^a-z0-9=_,]", "", x_maillens_timing.lower())[:300]
        log.info("analyze id=%s verdict=%s gate=%s vector=%s signals=%s%s", request_id, resp.verdict,
                 resp.gate or "-", decision.vector.replace(" · ", ","),
                 ",".join(sorted({f.signal for f in decision.kept})) or "-", demo)
        return resp

    if DEV:
        # Developer-only: the add-on's feasibility probe reports gate results here so they
        # can be checked without screenshots. Contains counts/timings, never email content.
        probe_file = Path(__file__).resolve().parents[2] / ".run" / "probe.json"

        @app.post("/v1/dev/probe-report", dependencies=[Depends(require_key)])
        def probe_report(report: list[dict[str, str | bool | None]]) -> dict[str, str]:
            probe_file.parent.mkdir(exist_ok=True)
            probe_file.write_text(json.dumps(report[:50], indent=2))
            log.info("probe report received gates=%d", len(report))
            return {"status": "stored"}

    return app


app = create_app()
