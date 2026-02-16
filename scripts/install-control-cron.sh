#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_LINE="* * * * * $ROOT/scripts/run-control.shz poll >> /tmp/control.out 2>&1"

existing=$(crontab -l 2>/dev/null || true)
if echo "$existing" | grep -q "run-control.sh poll"; then
  echo "Control poll cron entry already present."
  exit 0
fi

(crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
echo "Added control poll cron entry."
