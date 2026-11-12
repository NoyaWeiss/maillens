# MailLens backend + Security Console. Build from the repo root:
#   docker build -f backend/Dockerfile -t maillens-backend .
# Stateless analysis, no outbound calls, non-root. The only state is the per-account dashboard history
# in /data (mount a volume to keep it across restarts; it expires after 30 days).

# 1) Dashboard (static files; Node is needed only at build time)
FROM node:20-alpine AS dashboard
WORKDIR /d
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

# 2) Backend
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 \
    MAILLENS_EVAL_DIR=/srv/eval MAILLENS_DASHBOARD_DIR=/srv/dashboard MAILLENS_DATA_DIR=/data
WORKDIR /srv

# Exact, hash-pinned dependencies exported from uv.lock (uv export --no-dev).
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY backend/app ./app
COPY eval/metrics.json ./eval/metrics.json
COPY --from=dashboard /d/dist ./dashboard
RUN useradd --create-home --uid 10001 maillens && mkdir /data && chown maillens /data
USER maillens

# Behind a tunnel or proxy, trust X-Forwarded-For so the per-client rate limit sees real clients.
# Developer mode (MAILLENS_DEV_PROBE) is never set here.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --proxy-headers --forwarded-allow-ips="*" --no-server-header
