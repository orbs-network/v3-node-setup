#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="/usr/local/bin:/usr/bin:/bin${PATH:+:$PATH}"

set -a
[ -f "$ROOT/.env" ] && . "$ROOT/.env"
set +a

export BASE_DIR="$ROOT"
export DOCKER_COMPOSE_FILE="$ROOT/docker-compose.yml"

VENV="$ROOT/control/.venv"
if [ ! -d "$VENV" ]; then
  echo "Creating control venv..."
  python3 -m venv "$VENV"
  "$VENV/bin/python3" -m pip install -q -r "$ROOT/control/requirements.txt"
fi

"$VENV/bin/python3" "$ROOT/control/src/main.py" "$@"
