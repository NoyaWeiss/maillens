#!/usr/bin/env bash
# Create and push the demo-mailbox seeder (a separate Apps Script project whose only Gmail scope is
# gmail.insert). Dates are regenerated now so history stays inside the 180-day relationship window.
# Requires: python3, `clasp login` (its token is reused for the Apps Script API).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 demo/build_seed.py
if [ ! -f seeder/.clasp.json ]; then
  SID=$(python3 scripts/gas_api.py create "MailLens Demo Seeder")
  printf '{"scriptId":"%s","rootDir":"."}\n' "$SID" > seeder/.clasp.json
fi
SID=$(python3 -c "import json;print(json.load(open('seeder/.clasp.json'))['scriptId'])")
python3 scripts/gas_api.py push "$SID" seeder
echo "== open https://script.google.com/home/projects/$SID/edit , choose seedDemoMailbox, click Run (once)"
