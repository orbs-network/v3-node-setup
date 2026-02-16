#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_LINE="* * * * * $ROOT/scripts/run-control.sh poll >> /tmp/control.out 2>&1"

existing=$(crontab -l 2>/dev/null || true)
if echo "$existing" | grep -v '^[[:space:]]*#' | grep -q 'run-control'; then
  echo "Control poll cron entry already present (active run-control line found)."
  exit 0
fi

(crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
echo "Added control poll cron entry."
