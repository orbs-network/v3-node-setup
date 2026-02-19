#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=install-common.sh
. "$ROOT/scripts/install-common.sh"
CONTROL_LOG_PATH="$ROOT/.data/control/log.txt"
CRON_LINE="* * * * * $ROOT/scripts/run-control.sh poll >> $CONTROL_LOG_PATH 2>&1"
mkdir -p "$(dirname "$CONTROL_LOG_PATH")"

existing=$(crontab -l 2>/dev/null || true)
if echo "$existing" | grep -Fqx "$CRON_LINE"; then
  step_ok "Control poll cron entry already present."
  exit 0
fi

(echo "$existing" | grep -v 'run-control\.sh poll' || true; echo "$CRON_LINE") | crontab -
step_ok "Added/updated control poll cron entry."
