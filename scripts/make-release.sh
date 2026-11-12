#!/usr/bin/env bash
# Builds final/: a clean, self-contained release = exactly the committed source tree (HEAD), without .git,
# local state (.env, .clasp.json, Secrets.js, history database, logs) or build output (node_modules, dist).
#   scripts/make-release.sh          export HEAD into final/ (final/ must not exist yet)
#   scripts/make-release.sh --check  verify that final/ matches HEAD exactly
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/final"
TMP="$(mktemp -d)"
git -C "$ROOT" archive HEAD -- . ':(exclude)final' | tar -x -C "$TMP"
if [ "${1:-}" = "--check" ]; then
  diff -r "$TMP" "$OUT" >/dev/null && echo "final/ matches HEAD" || { echo "final/ differs from HEAD:"; diff -rq "$TMP" "$OUT" | head; exit 1; }
  exit 0
fi
[ -e "$OUT" ] && { echo "final/ already exists; move it aside first (it is regenerated from HEAD)"; exit 1; }
mv "$TMP" "$OUT"
echo "exported $(find "$OUT" -type f | wc -l | tr -d ' ') files to final/"
