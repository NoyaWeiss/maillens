#!/usr/bin/env bash
# Start the backend locally and expose it via a Cloudflare quick tunnel (dev/demo fallback).
# Prints the public URL to paste into the add-on's "Backend settings" card.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$ROOT/.run"
"$ROOT/scripts/stop.sh" >/dev/null 2>&1 || true
cd "$ROOT/backend"
MAILLENS_DEV_PROBE=1 uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8787 > "$ROOT/.run/backend.log" 2>&1 &
echo $! > "$ROOT/.run/backend.pid"
cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8787 > "$ROOT/.run/tunnel.log" 2>&1 &
echo $! > "$ROOT/.run/tunnel.pid"
URL=""
for _ in $(seq 1 30); do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$ROOT/.run/tunnel.log" | head -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
echo "${URL:?tunnel did not come up; see .run/tunnel.log}" | tee "$ROOT/.run/url"
