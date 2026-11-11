#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for f in backend tunnel; do
  [ -f "$ROOT/.run/$f.pid" ] && kill "$(cat "$ROOT/.run/$f.pid")" 2>/dev/null
  rm -f "$ROOT/.run/$f.pid"
done
echo stopped
