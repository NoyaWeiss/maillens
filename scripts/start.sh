#!/usr/bin/env bash
# Start MailLens again, or restore Gmail analysis after a restart, sleep or a stopped tunnel. Safe to re-run.
#   ~/maillens/scripts/start.sh
# Run scripts/setup.sh once first. This script never rebuilds, never creates an Apps Script project and never
# signs in to Google: it only (1) starts this checkout's backend container, (2) reuses the HTTPS tunnel if it
# still works or starts a new one, (3) re-points YOUR add-on at the new URL (only if the URL changed, and only
# with the Google account recorded at setup), then (4) checks the whole path end to end.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.tools/bin:$PATH"   # tools installed by scripts/install-tools.sh
B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'
ok()   { printf "${G}✓${N} %s\n" "$1"; }
fail() { printf "${R}✗ %s${N}\n" "$1"; exit 1; }
[ -f backend/.env ] && [ -f .clasp.json ] || fail "MailLens isn't set up in $ROOT yet: run $ROOT/scripts/setup.sh"

# 1) Backend: this checkout's own container (found by its label, so custom names and ports keep working).
if ! docker info >/dev/null 2>&1; then
  [ "$(uname)" = Darwin ] && open -a Docker 2>/dev/null && echo "starting Docker Desktop..."
  for _ in $(seq 1 45); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || fail "Docker is not running: open Docker Desktop, wait until it is running, then re-run."
fi
NAME="$(docker ps -a --filter "label=maillens.root=$ROOT" --format '{{.Names}}' | head -1)"
[ -n "$NAME" ] || fail "no MailLens container for $ROOT: run $ROOT/scripts/setup.sh"
docker start "$NAME" >/dev/null || fail "could not start container $NAME; see: docker logs $NAME"
export MAILLENS_PORT="$(docker port "$NAME" 8080/tcp | head -1 | sed 's/.*://')"
for _ in $(seq 1 20); do curl -fs -m 2 "http://127.0.0.1:$MAILLENS_PORT/healthz" >/dev/null && break; sleep 1; done
curl -fs -m 2 "http://127.0.0.1:$MAILLENS_PORT/healthz" >/dev/null || fail "backend not answering; see: docker logs $NAME"
ok "backend running ($NAME, http://127.0.0.1:$MAILLENS_PORT)"

# 2) HTTPS tunnel: keep the current URL while it works; otherwise start a new quick tunnel.
healthy() { [ "$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$1/healthz")" = "200" ]; }
if [ -n "${MAILLENS_TUNNEL_URL:-}" ]; then
  URL="${MAILLENS_TUNNEL_URL%/}"; echo "$URL" > .run/url
elif [ -f .run/url ] && healthy "$(cat .run/url)"; then
  URL="$(cat .run/url)"
else
  ./scripts/start-tunnel.sh >/dev/null || fail "the tunnel did not become reachable; see .run/tunnel.log, then re-run."
  URL="$(cat .run/url)"
fi
ok "public URL: $URL"

# 3) Add-on: push only when its approved URL differs, and only as the account that owns the project.
if [ "$(cat .run/addon-url 2>/dev/null)" != "$URL" ]; then
  CLASP_USER="${MAILLENS_CLASP_USER:-$(cat .run/clasp-user 2>/dev/null || echo maillens)}"
  OWNER="$(cat .run/clasp-project-account 2>/dev/null)"
  ACCOUNT="$(clasp --user "$CLASP_USER" show-authorized-user 2>/dev/null | sed -n 's/.*logged in as \(.*\)\.$/\1/p')"
  [ -n "$OWNER" ] && [ "$ACCOUNT" = "$OWNER" ] || fail "the MailLens Google login (${ACCOUNT:-none}) doesn't match the account that owns this add-on (${OWNER:-unknown}); run $ROOT/scripts/setup.sh"
  echo "re-pointing your add-on to $URL (account $ACCOUNT)..."
  MAILLENS_BUILD=prod MAILLENS_CLASP_USER="$CLASP_USER" ./scripts/push-addon.sh "$URL" >/dev/null 2>&1 \
    || fail "the add-on upload failed: run $ROOT/scripts/push-addon.sh $URL to see why"
  ok "add-on now uses $URL"
else
  ok "add-on already uses $URL"
fi

# 4) End to end: an authenticated request through the public URL, exactly as the add-on makes it.
KEY="$(grep '^MAILLENS_API_KEY=' backend/.env | cut -d= -f2-)"
[ "$(curl -s -o /dev/null -w '%{http_code}' -m 15 -H "X-API-Key: $KEY" "$URL/v1/status")" = "200" ] \
  || fail "$URL/v1/status did not accept the API key; re-run this script"
ok "analysis service reachable with your API key"
printf "\n${G}${B}MailLens is ready.${N} Reload Gmail and open an email. Dashboard: %s/dashboard/\n" "$URL"
