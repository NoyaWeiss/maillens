#!/usr/bin/env bash
# Stop MailLens: the tunnel, a scripts/dev.sh backend, and this checkout's Docker container.
# Your data (API key, dashboard history volume, Apps Script project) is kept. Start again: scripts/start.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for f in backend tunnel; do
  [ -f "$ROOT/.run/$f.pid" ] && kill "$(cat "$ROOT/.run/$f.pid")" 2>/dev/null
  rm -f "$ROOT/.run/$f.pid"
done
# Only this checkout's own container (labelled by run-backend-docker.sh); never removed, only stopped.
if docker info >/dev/null 2>&1; then
  for c in $(docker ps --filter "label=maillens.root=$ROOT" --format '{{.Names}}'); do docker stop "$c" >/dev/null && echo "stopped container $c"; done
fi
echo stopped
