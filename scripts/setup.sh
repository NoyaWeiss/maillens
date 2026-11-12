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
cd "$ROOT"                       # works from any directory: ~/maillens/scripts/setup.sh
export PATH="$ROOT/.tools/bin:$PATH"   # tools installed by scripts/install-tools.sh
MODE="${1:-}"
B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
step() { printf "\n${B}== %s${N}\n" "$1"; }
ok()   { printf "${G}✓${N} %s\n" "$1"; }
todo() { printf "${Y}➜${N} %s\n" "$1"; }
fail() { printf "${R}✗ %s${N}\n" "$1"; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || { MISSING+=("$1: $2"); return 1; }; }

step "1/4 Checking prerequisites"
MISSING=()
CLT="macOS: run  xcode-select --install  (Apple Command Line Tools); Linux: install it with your package manager"
need docker "Docker Desktop: https://www.docker.com/products/docker-desktop/ (install, open it once, wait until it says 'running')"
need python3 "python3 -> $CLT"
need curl "curl -> $CLT"
need tar "tar -> $CLT"
[ ${#MISSING[@]} -eq 0 ] || { printf "${R}Install these first (setup can't do it for you):${N}\n"; printf "  - %s\n" "${MISSING[@]}"; fail "then re-run: $ROOT/scripts/setup.sh"; }
docker info >/dev/null 2>&1 || fail "Docker is installed but not running: open Docker Desktop, wait until it is running, then re-run."
TOOLS=()
[ -z "${MAILLENS_TUNNEL_URL:-}" ] && TOOLS+=(cloudflared)
[ "$MODE" != "--backend-only" ] && TOOLS+=(node clasp)
[ ${#TOOLS[@]} -eq 0 ] || ./scripts/install-tools.sh "${TOOLS[@]}" || fail "a required tool could not be installed (see above)"
ok "prerequisites ready"

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
# MailLens uses its OWN named clasp login (never your default clasp login), and you confirm the account.
CLASP_USER="${MAILLENS_CLASP_USER:-$(cat .run/clasp-user 2>/dev/null || { [ -f .clasp.json ] && echo default || echo maillens; })}"
echo "$CLASP_USER" > .run/clasp-user
acct() { clasp --user "$CLASP_USER" show-authorized-user 2>/dev/null | sed -n 's/.*logged in as \(.*\)\.$/\1/p'; }
confirm() { read -r -p "   MailLens will use the Google account $1. Is this your TEST account? [y/N] " a || fail "No terminal to confirm the Google account: run in Terminal, or set MAILLENS_GOOGLE_ACCOUNT=<email>."; [ "$a" = y ] || [ "$a" = Y ]; }
ACCOUNT="$(acct)"
if [ -n "$ACCOUNT" ]; then
  if [ -n "${MAILLENS_GOOGLE_ACCOUNT:-}" ]; then [ "$ACCOUNT" = "$MAILLENS_GOOGLE_ACCOUNT" ] || { clasp --user "$CLASP_USER" logout >/dev/null; ACCOUNT=""; }
  elif ! confirm "$ACCOUNT"; then clasp --user "$CLASP_USER" logout >/dev/null; ACCOUNT=""; fi
fi
if [ -z "$ACCOUNT" ]; then
  todo "Google sign-in: a browser opens. Choose your TEST account (click 'Use another account' if it isn't listed), then Allow."
  read -r -p "   Press Enter to open the browser... " _ || fail "Google login needs an interactive terminal: run $ROOT/scripts/setup.sh in Terminal."
  clasp --user "$CLASP_USER" login || fail "Google sign-in did not complete; re-run $ROOT/scripts/setup.sh"
  ACCOUNT="$(acct)"; [ -n "$ACCOUNT" ] || fail "could not read the signed-in account; re-run $ROOT/scripts/setup.sh"
  [ -n "${MAILLENS_GOOGLE_ACCOUNT:-}" ] && { [ "$ACCOUNT" = "$MAILLENS_GOOGLE_ACCOUNT" ] || fail "signed in as $ACCOUNT, expected $MAILLENS_GOOGLE_ACCOUNT"; } || confirm "$ACCOUNT" || fail "re-run $ROOT/scripts/setup.sh and sign in with your test account"
fi
ok "Google account: $ACCOUNT"
# The Apps Script project must belong to this account: otherwise keep the old one aside and create a new one.
if [ -f .clasp.json ] && [ "$(cat .run/clasp-project-account 2>/dev/null)" != "$ACCOUNT" ]; then
  TS=$(date +%Y%m%d%H%M%S); mv .clasp.json ".run/old-project-$TS.clasp.json"; [ -f .run/scan-deployment-id ] && mv .run/scan-deployment-id ".run/old-scan-deployment-$TS"
  todo "the existing Apps Script project wasn't created with $ACCOUNT; a new project will be created (old reference kept in .run/)"
fi
OUT="$(./scripts/setup-addon.sh "$URL" 2>&1)"; STATUS=$?
echo "$OUT" | grep -E "allow-list|Pushed|Install it" | sed 's/^/   /'
if [ $STATUS -ne 0 ]; then
  if echo "$OUT" | grep -qi "usersettings\|Apps Script API"; then
    todo "Turn ON 'Google Apps Script API' at https://script.google.com/home/usersettings (wait ~1 minute), then re-run $ROOT/scripts/setup.sh"
    exit 1
  fi
  echo "$OUT" | tail -5; fail "the add-on upload failed (details above); fix and re-run $ROOT/scripts/setup.sh"
fi
SID="$(python3 -c "import json;print(json.load(open('.clasp.json'))['scriptId'])")"
echo "$ACCOUNT" > .run/clasp-project-account
ok "add-on uploaded to your Apps Script project"

if [ "$MODE" = "--with-demo" ]; then
  step "Optional: synthetic demo mailbox"
  ./scripts/setup-seeder.sh 2>&1 | tail -2 | sed 's/^/   /'
fi

printf "\n${G}${B}Automated setup complete.${N} Two manual steps remain (Google requires them):\n"
printf "  1. Open https://script.google.com/home/projects/%s/edit\n" "$SID"
printf "     -> Deploy -> Test deployments -> Install -> Done\n"
printf "  2. In Gmail (reload it), open any email and click the MailLens icon in the right-hand panel\n"
printf "     -> Authorize access -> 'Google hasn't verified this app' -> Advanced -> Go to MailLens -> Allow\n"
printf "\nSuccess looks like: the MailLens Home screen says 'Analysis service ready', and an opened email shows a verdict.\n"
[ "$MODE" = "--with-demo" ] && printf "Demo mailbox: open the seeder link above, choose seedDemoMailbox, click Run once.\n"
printf "If the tunnel restarts later, re-run $ROOT/scripts/setup.sh (it re-points the add-on to the new URL).\n"
