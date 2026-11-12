#!/usr/bin/env bash
# MailLens guided setup: the one command to run after cloning. Safe to re-run at any time.
#
#   ./scripts/setup.sh                  full setup: backend + dashboard, HTTPS tunnel, Gmail add-on
#   ./scripts/setup.sh --with-demo      also creates the synthetic demo mailbox (optional)
#   ./scripts/setup.sh --backend-only   backend + dashboard + tunnel only (nothing touches Google)
#
# Use your own HTTPS endpoint instead of a Cloudflare quick tunnel:
#   MAILLENS_TUNNEL_URL=https://your-host.example ./scripts/setup.sh
#
# Automated: prerequisite checks, a new random API key (backend/.env, never printed), Docker build and
# start, the tunnel, Apps Script project creation and upload. Manual (Google requires it): clasp login,
# enabling the Apps Script API, installing the test deployment, and authorizing the add-on in Gmail.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${1:-}"
B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
step() { printf "\n${B}== %s${N}\n" "$1"; }
ok()   { printf "${G}✓${N} %s\n" "$1"; }
todo() { printf "${Y}➜${N} %s\n" "$1"; }
fail() { printf "${R}✗ %s${N}\n" "$1"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || { MISSING+=("$1: $2"); return 1; }; }

step "1/4 Checking prerequisites"
MISSING=()
need docker "install Docker Desktop: https://www.docker.com/products/docker-desktop/"
need python3 "install Python 3.9+: https://www.python.org/downloads/"
need curl "install curl"
[ -z "${MAILLENS_TUNNEL_URL:-}" ] && need cloudflared "install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ (macOS: brew install cloudflared)"
if [ "$MODE" != "--backend-only" ]; then
  need node "install Node.js 18+: https://nodejs.org/"
  need clasp "install clasp: npm install -g @google/clasp"
fi
[ ${#MISSING[@]} -eq 0 ] || { printf "${R}Missing prerequisites:${N}\n"; printf "  - %s\n" "${MISSING[@]}"; fail "install the items above, then re-run ./scripts/setup.sh"; }
docker info >/dev/null 2>&1 || fail "Docker is installed but not running: start Docker Desktop, then re-run."
ok "prerequisites found"

step "2/4 Backend and dashboard (Docker, http://127.0.0.1:${MAILLENS_PORT:-8787})"
./scripts/run-backend-docker.sh || fail "the backend did not start; see: docker logs ${MAILLENS_CONTAINER:-maillens}"
ok "backend and dashboard running (API key stored in backend/.env, gitignored)"

step "3/4 HTTPS tunnel (Gmail can only reach HTTPS)"
mkdir -p .run
healthy() { [ "$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$1/healthz")" = "200" ]; }
if [ -n "${MAILLENS_TUNNEL_URL:-}" ]; then
  URL="${MAILLENS_TUNNEL_URL%/}"
  echo "$URL" > .run/url
  healthy "$URL" || todo "$URL does not answer /healthz yet; make sure it forwards to http://127.0.0.1:${MAILLENS_PORT:-8787}"
elif [ -f .run/url ] && healthy "$(cat .run/url)"; then
  URL="$(cat .run/url)"
else
  ./scripts/start-tunnel.sh >/dev/null || fail "the tunnel did not become reachable; see .run/tunnel.log, then re-run."
  URL="$(cat .run/url)"
fi
ok "public URL: $URL"

if [ "$MODE" = "--backend-only" ]; then
  printf "\n${G}${B}Backend ready.${N} Check: curl %s/healthz   Dashboard: %s/dashboard/\n" "$URL" "$URL"
  exit 0
fi

step "4/4 Gmail add-on (your own Apps Script project)"
if [ ! -f "$HOME/.clasprc.json" ]; then
  todo "Google login needed once: a browser window opens for 'clasp login'. Use your TEST Google account."
  read -r -p "   Press Enter to continue... " _
  clasp login || fail "clasp login did not complete; re-run ./scripts/setup.sh"
fi
OUT="$(./scripts/setup-addon.sh "$URL" 2>&1)"; STATUS=$?
echo "$OUT" | grep -E "allow-list|Pushed|Install it" | sed 's/^/   /'
if [ $STATUS -ne 0 ]; then
  if echo "$OUT" | grep -qi "usersettings\|Apps Script API"; then
    todo "Turn ON 'Google Apps Script API' at https://script.google.com/home/usersettings (wait ~1 minute), then re-run ./scripts/setup.sh"
    exit 1
  fi
  echo "$OUT" | tail -5; fail "the add-on upload failed (details above); fix and re-run ./scripts/setup.sh"
fi
SID="$(python3 -c "import json;print(json.load(open('.clasp.json'))['scriptId'])")"
ok "add-on uploaded to your Apps Script project"

if [ "$MODE" = "--with-demo" ]; then
  step "Optional: synthetic demo mailbox"
  ./scripts/setup-seeder.sh 2>&1 | tail -2 | sed 's/^/   /'
fi

printf "\n${G}${B}Automated setup complete.${N} Two manual steps remain (Google requires them):\n"
printf "  1. Open https://script.google.com/home/projects/%s/edit\n" "$SID"
printf "     -> Deploy -> Test deployments -> Application(s): Gmail -> Install\n"
printf "  2. In Gmail (reload it), open any email and click the MailLens icon in the right-hand panel\n"
printf "     -> Authorize access -> 'Google hasn't verified this app' -> Advanced -> Go to MailLens -> Allow\n"
printf "\nSuccess looks like: the MailLens Home screen says 'Analysis service ready', and an opened email shows a verdict.\n"
[ "$MODE" = "--with-demo" ] && printf "Demo mailbox: open the seeder link above, choose seedDemoMailbox, click Run once.\n"
printf "If the tunnel restarts later, re-run ./scripts/setup.sh (it re-points the add-on to the new URL).\n"
