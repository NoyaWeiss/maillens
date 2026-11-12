#!/usr/bin/env bash
# Expose the local backend over HTTPS with a free Cloudflare quick tunnel (no account needed).
# Prints the public URL and saves it to .run/url. Requires: cloudflared.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.run"
[ -f "$ROOT/.run/tunnel.pid" ] && kill "$(cat "$ROOT/.run/tunnel.pid")" 2>/dev/null || true
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${MAILLENS_PORT:-8787}" > "$ROOT/.run/tunnel.log" 2>&1 &
echo $! > "$ROOT/.run/tunnel.pid"
URL=""
for _ in $(seq 1 30); do
  URL=$(LC_ALL=C grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$ROOT/.run/tunnel.log" | tail -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "$URL" ] || { echo "tunnel did not start; see .run/tunnel.log"; exit 1; }
echo "$URL" | tee "$ROOT/.run/url"
echo "Note: quick-tunnel URLs change on every restart; re-run scripts/setup-addon.sh afterwards."
