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
NAME="${MAILLENS_CONTAINER:-maillens}"; PORT="${MAILLENS_PORT:-8787}"; VOL="${MAILLENS_VOLUME:-maillens-data}"
# Never touch another MailLens checkout's container or volume, or a port something else is using. Each checkout
# labels its own; to run a second copy side by side, set MAILLENS_CONTAINER, MAILLENS_PORT and MAILLENS_VOLUME.
other() { echo "Refusing: $1 belongs to another MailLens checkout or app. Set MAILLENS_CONTAINER, MAILLENS_PORT and MAILLENS_VOLUME to run this copy separately."; exit 1; }
if docker container inspect "$NAME" >/dev/null 2>&1; then
  [ "$(docker container inspect -f '{{index .Config.Labels "maillens.root"}}' "$NAME" 2>/dev/null)" = "$ROOT" ] || other "container '$NAME'"
fi
if docker volume inspect "$VOL" >/dev/null 2>&1; then
  [ "$(docker volume inspect -f '{{index .Labels "maillens.root"}}' "$VOL" 2>/dev/null)" = "$ROOT" ] || other "volume '$VOL'"
fi
docker build -q -f "$ROOT/backend/Dockerfile" -t maillens-backend "$ROOT" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true   # only ever this checkout's own container (checked above)
curl -s -o /dev/null -m 2 "http://127.0.0.1:$PORT/" && other "port $PORT (already in use)"
docker volume inspect "$VOL" >/dev/null 2>&1 || docker volume create --label "maillens.root=$ROOT" "$VOL" >/dev/null
# Bound to localhost only: the public HTTPS entry point is your own tunnel (scripts/start-tunnel.sh).
docker run -d --name "$NAME" --label "maillens.root=$ROOT" --restart unless-stopped -p "127.0.0.1:$PORT:8080" --env-file "$ENV" -v "$VOL":/data maillens-backend >/dev/null
for _ in $(seq 1 20); do curl -fs http://127.0.0.1:${MAILLENS_PORT:-8787}/healthz >/dev/null 2>&1 && break; sleep 1; done
curl -fs "http://127.0.0.1:${MAILLENS_PORT:-8787}/healthz" && echo "  <- backend is up on http://127.0.0.1:${MAILLENS_PORT:-8787}"
