"""MailLens backend: no outbound network calls. Analysis is stateless; the only state is the opt-in,
per-account analysis history used by the Security Console (app/history.py)."""

import json
import re
import logging
import os
import time
import uuid
from pathlib import Path
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import engine, evaluation
from .history import History
from .config import Settings, load_settings
from .schemas import AnalyzeRequest, AnalyzeResponse
from .security import BodySizeLimit, RateLimiter, check_api_key

log = logging.getLogger("maillens")
DEV = os.environ.get("MAILLENS_DEV_PROBE") == "1"
# Synthetic demo-mailbox Message-IDs only (see demo/build_seed.py); real mail never matches.
_DEMO_ID = re.compile(r"^<([a-z0-9]{1,8})\.maillens-demo@mail\.example>$")
_ACCOUNT_KEY = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
# Gmail's add-on message id is opaque (it is not always the 16-hex Gmail API id; it can carry a prefix
# such as "msg-f:"). It is only ever HMAC'd, never parsed or displayed, so accept any printable token.
_GMAIL_ID = re.compile(r"^[!-~]{1,200}$")


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
                               "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
    "Cache-Control": "no-store",
}


class LaunchRequest(BaseModel):
    account: str = Field(pattern=_ACCOUNT_KEY.pattern)
    message: str | None = Field(default=None, pattern=_GMAIL_ID.pattern)
    label: str = Field(default="", max_length=80)


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

    def require_session(request: Request, authorization: str | None = Header(default=None)) -> tuple[str, str | None, str]:
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
                x_maillens_message: str | None = Header(default=None)) -> AnalyzeResponse:
        request_id = uuid.uuid4().hex[:12]
        resp, decision = engine.analyze(req, request_id)
        # Account history (dashboard): only when the add-on sends a well-formed account key and message id.
        acct_ok = bool(x_maillens_account and _ACCOUNT_KEY.match(x_maillens_account))
        msg_ok = bool(x_maillens_message and _GMAIL_ID.match(x_maillens_message))
        if acct_ok and msg_ok:
            history.record(x_maillens_account, x_maillens_message, req.message.subject or "(no subject)",
                           req.message.from_header or "", resp.model_dump(mode="json"))
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
        code = history.mint_code(body.account, body.message, body.label)
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
        acct, context, label = s
        return {"emails": history.list(acct), "context": context, "account_label": label,
                "retention_days": 30, "now": time.time()}

    @app.get("/v1/dashboard/emails/{ref}")
    def dashboard_email(ref: str, s=Depends(require_session)) -> dict:
        item = history.get(s[0], ref) if re.fullmatch(r"[0-9a-f]{32}", ref) else None
        if not item:  # same answer for "not yours" and "doesn't exist"
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        return item

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
