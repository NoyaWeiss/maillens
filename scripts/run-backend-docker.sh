#!/usr/bin/env bash
# Build and run the MailLens backend + Security Console in Docker on http://127.0.0.1:8787 (production mode).
# Dashboard history is kept in the Docker volume "maillens-data" (1-year retention).
# Creates backend/.env with a fresh random API key if it doesn't exist. Requires: Docker, python3.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$ROOT/backend/.env"
if [ ! -f "$ENV" ]; then
  (umask 077; printf 'MAILLENS_API_KEY=%s\n' "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" > "$ENV")
  echo "created backend/.env with a new random API key (file mode 600, gitignored)"
fi
docker build -q -f "$ROOT/backend/Dockerfile" -t maillens-backend "$ROOT" >/dev/null
docker rm -f "${MAILLENS_CONTAINER:-maillens}" >/dev/null 2>&1 || true
# Bound to localhost only: the public HTTPS entry point is your own tunnel (scripts/start-tunnel.sh).
docker run -d --name "${MAILLENS_CONTAINER:-maillens}" --restart unless-stopped -p "127.0.0.1:${MAILLENS_PORT:-8787}:8080" --env-file "$ENV" -v "${MAILLENS_VOLUME:-maillens-data}":/data maillens-backend >/dev/null
for _ in $(seq 1 20); do curl -fs http://127.0.0.1:${MAILLENS_PORT:-8787}/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fs "http://127.0.0.1:${MAILLENS_PORT:-8787}/healthz" && echo "  <- backend is up on http://127.0.0.1:${MAILLENS_PORT:-8787}"
