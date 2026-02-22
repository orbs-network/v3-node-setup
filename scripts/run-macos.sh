#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=install-common.sh
. "$ROOT/scripts/install-common.sh"

cd "$ROOT"

ENV_FILE="$ROOT/.env"
COMPOSE_FILE="$ROOT/docker-compose.yml"

if [ ! -f "$ENV_FILE" ] && [ -f "$ROOT/.env.template" ]; then
  step "No .env found; copying .env.template to .env"
  cp "$ROOT/.env.template" "$ENV_FILE"
fi

if [ ! -d "$ROOT/scripts/venv" ]; then
  step "Creating scripts venv..."
  python3 -m venv "$ROOT/scripts/venv" 2>/dev/null || { python3 -m venv "$ROOT/scripts/venv" 2>&1; exit 1; }
fi
run_silent "Installing Python dependencies..." bash -c "\"$ROOT/scripts/venv/bin/python3\" -m pip install -q \"setuptools<82\" && \"$ROOT/scripts/venv/bin/python3\" -m pip install -q -r \"$ROOT/scripts/requirements.txt\""
step "Setup: node key and guardian details."
echo
"$ROOT/scripts/venv/bin/python3" "$ROOT/scripts/prompt_and_env.py"

if [ -f "$ENV_FILE" ]; then
  if ! grep -qE "^BASE_DIR=.+" "$ENV_FILE" 2>/dev/null; then
    echo "BASE_DIR=$ROOT" >> "$ENV_FILE"
    step_ok "Added BASE_DIR to .env"
  fi
  if [ -f "$COMPOSE_FILE" ] && ! grep -qE "^DOCKER_COMPOSE_FILE=.+" "$ENV_FILE" 2>/dev/null; then
    echo "DOCKER_COMPOSE_FILE=$ROOT/docker-compose.yml" >> "$ENV_FILE"
    step_ok "Added DOCKER_COMPOSE_FILE to .env"
  fi
fi

success_msg "macOS setup done. .env and keys are ready. Use make [CMD] to run commands."
echo
