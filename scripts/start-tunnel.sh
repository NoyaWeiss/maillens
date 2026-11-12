#!/usr/bin/env bash
# Expose the local backend over HTTPS with a free Cloudflare quick tunnel (no account needed).
# Prints the public URL and saves it to .run/url. Requires: cloudflared. Survives closing the Terminal window
# (nohup), but not a restart or sleep: then run scripts/start.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/.run"
[ -f "$ROOT/.run/tunnel.pid" ] && kill "$(cat "$ROOT/.run/tunnel.pid")" 2>/dev/null || true
nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:${MAILLENS_PORT:-8787}" > "$ROOT/.run/tunnel.log" 2>&1 &
echo $! > "$ROOT/.run/tunnel.pid"
URL=""
for _ in $(seq 1 30); do
  URL=$(LC_ALL=C grep -aoE 'https://[a-z0-9-]+\.trycloudflare\.com' "$ROOT/.run/tunnel.log" | tail -1 || true)
  [ -n "$URL" ] && break; sleep 1
done
[ -n "$URL" ] || { echo "tunnel did not start; see .run/tunnel.log"; exit 1; }
echo "$URL" > "$ROOT/.run/url"
printf "waiting for the public URL to resolve (new quick-tunnel hostnames can take 1-2 minutes)"
for _ in $(seq 1 36); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 "$URL/healthz")" = "200" ] && break; printf "."; sleep 5
done
echo
[ "$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$URL/healthz")" = "200" ] || { echo "tunnel not reachable yet: $URL (check .run/tunnel.log)"; exit 1; }
echo "$URL"
echo "Note: quick-tunnel URLs change on every restart; run scripts/start.sh to re-point the add-on."
