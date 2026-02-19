#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=install-common.sh
. "$ROOT/scripts/install-common.sh"
CRON_LINE="* * * * * $ROOT/scripts/run-control.sh poll >> /tmp/control.out 2>&1"

existing=$(crontab -l 2>/dev/null || true)
if echo "$existing" | grep -v '^[[:space:]]*#' | grep -q 'run-control'; then
  step_ok "Control poll cron entry already present."
  exit 0
fi

(crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
step_ok "Added control poll cron entry."
