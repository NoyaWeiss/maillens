"""MailLens backend: no outbound network calls. Analysis is stateless; the only state is the opt-in,
per-account analysis history used by the Security Console (app/history.py)."""

import json
import re
import logging
import os
import time
import uuid
from email.utils import parsedate_to_datetime
from pathlib import Path
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine, evaluation
from .history import SCAN_LIMIT, History
from .config import Settings, load_settings
from .schemas import AnalyzeRequest, AnalyzeResponse
from .security import BodySizeLimit, RateLimiter, check_api_key

log = logging.getLogger("maillens")
DEV = os.environ.get("MAILLENS_DEV_PROBE") == "1"
# Synthetic demo-mailbox Message-IDs only (see demo/build_seed.py); real mail never matches.
_DEMO_ID = re.compile(r"^<([a-z0-9]{1,8})\.maillens-demo@mail\.example>$")
_ACCOUNT_KEY = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_SCAN_URL = r"^https://script\.google\.com/macros/s/[A-Za-z0-9_-]{20,120}/(exec|dev)$"
# Gmail's add-on message id is opaque (it is not always the 16-hex Gmail API id; it can carry a prefix
# such as "msg-f:"). It is only ever HMAC'd, never parsed or displayed, so accept any printable token.
_GMAIL_ID = re.compile(r"^[!-~]{1,200}$")


def received_time(header_ms: str | None, date_header: str | None) -> float | None:
    """When the email arrived, as UTC epoch seconds. Gmail's received timestamp (sent by the add-on as
    X-MailLens-Received, from internalDate / getDate) wins; otherwise the email's Date header, honoring its
    timezone; otherwise unknown (None). Never the analysis time: time filters must not depend on it."""
    if header_ms and header_ms.isdigit():
        return int(header_ms) / 1000
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            return dt.timestamp() if dt.tzinfo else None
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    return None


def _shape(value: str) -> str:
    """Character-class outline of an identifier for diagnostics: e.g. 'a3-a1:d19'. Never the value itself."""
    out, prev, n = [], "", 0
    for ch in value[:200]:
        c = "d" if ch.isdigit() else "a" if ch.isalpha() else ch
        if c == prev and c in "ad":
            n += 1
            continue
        if prev:
            out.append(prev + (str(n) if prev in "ad" else ""))
        prev, n = c, 1
    if prev:
        out.append(prev + (str(n) if prev in "ad" else ""))
    return "".join(out)[:60]
_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("MAILLENS_DATA_DIR", _ROOT / "backend" / "data"))
DASHBOARD_DIR = Path(os.environ.get("MAILLENS_DASHBOARD_DIR", _ROOT / "dashboard" / "dist"))
_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                               "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "
                               "frame-src https://script.google.com https://*.googleusercontent.com",  # inbox scan page (Apps Script)
    "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


class LaunchRequest(BaseModel):
    account: str = Field(pattern=_ACCOUNT_KEY.pattern)
    message: str | None = Field(default=None, pattern=_GMAIL_ID.pattern)
    label: str = Field(default="", max_length=80)
    scan_url: str | None = Field(default=None, pattern=_SCAN_URL)


RANGES = {"1H": 3600, "24H": 86400, "7D": 7 * 86400, "30D": 30 * 86400}


class ScanRequest(BaseModel):
    range: str = Field(pattern="^(1H|24H|7D|30D)$")


class ScanAuth(BaseModel):
    ticket: str = Field(min_length=20, max_length=64)
    account: str = Field(pattern=_ACCOUNT_KEY.pattern)


class ScanKnown(ScanAuth):
    ids: list[str] = Field(max_length=SCAN_LIMIT)


class ScanProgress(ScanAuth):
    state: str = Field(pattern="^(running|done|error|cancelled)$")
    total: int = Field(ge=0, le=SCAN_LIMIT)
    done: int = Field(ge=0, le=SCAN_LIMIT)
    skipped: int = Field(ge=0, le=SCAN_LIMIT)
    failed: int = Field(ge=0, le=SCAN_LIMIT)
    error: str = Field(default="", max_length=200)


class SessionRequest(BaseModel):
    code: str = Field(min_length=20, max_length=100)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@lru_cache
def get_settings() -> Settings:
    return load_settings()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MailLens", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    history = History(DATA_DIR / "history.sqlite3", settings.api_key)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(("/dashboard", "/v1/dashboard")):
            for k, v in _SECURITY_HEADERS.items():
                response.headers.setdefault(k, v)
        return response

    def require_session(request: Request, authorization: str | None = Header(default=None)) -> tuple[str, str | None, str, str]:
        limiter.check(request)
        token = (authorization or "").removeprefix("Bearer ").strip()
        s = history.session(token)
        if not s:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
        return s

    def require_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
        limiter.check(request)
        if not check_api_key(x_api_key, settings.api_key):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")

    @app.exception_handler(RequestValidationError)
    async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where validation failed, never the offending (attacker-controlled) value.
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()][:10]
        log.warning("validation failed path=%s fields=%s", _.url.path, ",".join(fields))
        return JSONResponse(status_code=422, content={"detail": "invalid request", "fields": fields})

    @app.exception_handler(Exception)
    async def on_error(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error type=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    @app.get("/v1/status", dependencies=[Depends(require_key)])
    def status_check() -> dict[str, str]:
        # Authenticated readiness check for the add-on's welcome screen: proves the service is
        # reachable AND the API key is accepted. Returns nothing else.
        return {"status": "ok"}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/analyze", response_model=AnalyzeResponse, dependencies=[Depends(require_key)])
    def analyze(req: AnalyzeRequest, x_maillens_timing: str | None = Header(default=None),
                x_maillens_account: str | None = Header(default=None),
                x_maillens_message: str | None = Header(default=None),
                x_maillens_received: str | None = Header(default=None)) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex[:12]
        resp, decision = engine.analyze(req, request_id)
        # Account history (dashboard): only when the add-on sends a well-formed account key and message id.
        acct_ok = bool(x_maillens_account and _ACCOUNT_KEY.match(x_maillens_account))
        msg_ok = bool(x_maillens_message and _GMAIL_ID.match(x_maillens_message))
        if acct_ok and msg_ok:
            history.record(x_maillens_account, x_maillens_message, req.message.subject or "(no subject)",
                           req.message.from_header or "", resp.model_dump(mode="json"),
                           received=received_time(x_maillens_received, req.message.date))
        elif x_maillens_account or x_maillens_message:  # sent but unusable: log shapes only, never values
            log.warning("history not recorded account=%s message=%s", "ok" if acct_ok else _shape(x_maillens_account or "") or "missing",
                        "ok" if msg_ok else _shape(x_maillens_message or "") or "missing")
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

    # ------------------------------------------------------------ Security Console (Phase 4)
    @app.post("/v1/dashboard/launch", dependencies=[Depends(require_key)])
    def dashboard_launch(body: LaunchRequest) -> dict[str, str]:
        # Called by the add-on at click time. The code goes in the URL fragment (never sent to servers or
        # logged), expires in 2 minutes and works once. No token, key or email content is in the URL.
        code = history.mint_code(body.account, body.message, body.label, body.scan_url or "")
        return {"path": f"/dashboard/#launch={code}"}

    @app.post("/v1/dashboard/session")
    def dashboard_session(body: SessionRequest, request: Request) -> dict:
        limiter.check(request)
        out = history.redeem(body.code)
        if not out:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "launch link expired or already used")
        token, info = out
        return {"token": token, **info}

    @app.get("/v1/dashboard/emails")
    def dashboard_emails(s=Depends(require_session)) -> dict:
        acct, context, label, _ = s
        return {"emails": history.list(acct), "context": context, "account_label": label, "scan_available": bool(s[3]),
                "retention_days": 30, "now": time.time()}

    @app.get("/v1/dashboard/emails/{ref}")
    def dashboard_email(ref: str, s=Depends(require_session)) -> dict:
        item = history.get(s[0], ref) if re.fullmatch(r"[0-9a-f]{32}", ref) else None
        if not item:  # same answer for "not yours" and "doesn't exist"
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return item

    # ---- Inbox scan. The dashboard can't read Gmail; the user's own Apps Script web app does (existing
    # gmail.readonly scope, runs as the signed-in user). The ticket ties the scan to this session's account:
    # the web app must present the private account key that hashes to the same account.
    @app.post("/v1/dashboard/scan")
    def dashboard_scan(body: ScanRequest, s=Depends(require_session)) -> dict:
        acct, _, _, scan_url = s
        if not scan_url:
            raise HTTPException(status.HTTP_409_CONFLICT, "inbox scanning is not set up for this add-on")
        ticket = history.mint_ticket(acct, RANGES[body.range])
        return {"ticket": ticket, "url": f"{scan_url}?t={ticket}", "limit": SCAN_LIMIT}

    @app.get("/v1/dashboard/scan/{ticket}")
    def dashboard_scan_status(ticket: str, s=Depends(require_session)) -> dict:
        p = history.progress(ticket, s[0])
        if p is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return p

    def _scan_ticket(body: ScanAuth) -> tuple[str, int]:
        t = history.ticket_for(body.ticket, body.account)
        if not t:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "scan ticket expired or belongs to a different Google account")
        return t

    @app.post("/v1/scan/start", dependencies=[Depends(require_key)])
    def scan_start(body: ScanAuth) -> dict:
        _, range_s = _scan_ticket(body)
        if not history.claim_start(body.ticket):
            raise HTTPException(status.HTTP_409_CONFLICT, "this scan is already running or finished")
        return {"range_seconds": range_s, "limit": SCAN_LIMIT}

    @app.post("/v1/scan/known", dependencies=[Depends(require_key)])
    def scan_known(body: ScanKnown) -> dict:
        acct, _ = _scan_ticket(body)
        return {"known": history.known_refs(acct, [i for i in body.ids if _GMAIL_ID.match(i)])}

    @app.post("/v1/scan/progress", dependencies=[Depends(require_key)])
    def scan_progress(body: ScanProgress) -> dict:
        _scan_ticket(body)
        history.update_progress(body.ticket, state=body.state, total=body.total, done=body.done,
                                skipped=body.skipped, failed=body.failed, error=body.error)
        # Counts and the first Apps Script error message (step + exception text), never email content.
        log.info("scan progress state=%s total=%d analyzed=%d skipped=%d failed=%d error=%s", body.state, body.total,
                 body.done, body.skipped, body.failed, re.sub(r"[^\x20-\x7e]", "?", body.error)[:160] or "-")
        return {"status": "ok"}

    @app.delete("/v1/dashboard/history")
    def dashboard_clear(s=Depends(require_session)) -> dict[str, int]:
        return {"deleted": history.clear(s[0])}

    @app.get("/v1/dashboard/evaluation")
    def dashboard_evaluation(request: Request) -> dict:
        limiter.check(request)
        try:
            return evaluation.load()
        except (OSError, KeyError, ValueError):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "evaluation results unavailable")

    if DASHBOARD_DIR.is_dir():
        @app.get("/dashboard", include_in_schema=False)
        def dashboard_root() -> RedirectResponse:
            return RedirectResponse("/dashboard/")

        app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

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
