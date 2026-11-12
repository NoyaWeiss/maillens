# MailLens backend: production image for Cloud Run (stateless, no outbound calls, non-root).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /srv

# Exact, hash-pinned dependencies exported from uv.lock (uv export --no-dev).
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY app ./app
RUN useradd --create-home --uid 10001 maillens
USER maillens

# Cloud Run terminates TLS and forwards the client address; trust its X-Forwarded-For so the
# per-client rate limit sees real clients. Developer mode (MAILLENS_DEV_PROBE) is never set here.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*" --no-server-header
