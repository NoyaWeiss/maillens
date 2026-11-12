#!/usr/bin/env bash
# Create (first run) and push YOUR Gmail add-on to YOUR Apps Script project, pointed at YOUR backend.
# Requires: Node + clasp (npm i -g @google/clasp), `clasp login`, Apps Script API enabled at
# https://script.google.com/home/usersettings, and a backend URL (default: .run/url from start-tunnel.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="${1:-$(cat "$ROOT/.run/url" 2>/dev/null || true)}"
[ -n "$URL" ] || { echo "usage: scripts/setup-addon.sh https://<your-backend-host>"; exit 1; }
cd "$ROOT"
if [ ! -f .clasp.json ]; then
  echo "== creating your Apps Script project (MailLens)"
  cp addon/appsscript.json .run/appsscript.keep.json 2>/dev/null || { mkdir -p .run; cp addon/appsscript.json .run/appsscript.keep.json; }
  clasp create-script --type standalone --title "${MAILLENS_PROJECT_TITLE:-MailLens}" --rootDir addon
  cp .run/appsscript.keep.json addon/appsscript.json   # clasp overwrites the manifest; restore ours
fi
MAILLENS_BUILD=prod "$ROOT/scripts/push-addon.sh" "$URL"
SID=$(python3 -c "import json;print(json.load(open('.clasp.json'))['scriptId'])")
echo "== done. Install it: https://script.google.com/home/projects/$SID/edit -> Deploy -> Test deployments -> Install"
