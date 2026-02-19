#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=install-common.sh
. "$ROOT/scripts/install-common.sh"

if [ "$EUID" -ne 0 ]; then
  err "Please run this setup with sudo (e.g. sudo ./scripts/run.sh or sudo make setup)."
fi

cd "$ROOT"

step "Checking and installing dependencies..."
"$ROOT/scripts/install-dependencies.sh"

ENV_FILE="$ROOT/.env"
COMPOSE_FILE="$ROOT/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
  err "docker-compose.yml not found at $COMPOSE_FILE"
fi

if [ ! -f "$ENV_FILE" ] && [ -f "$ROOT/.env.template" ]; then
  step "No .env found; copying .env.template to .env"
  cp "$ROOT/.env.template" "$ENV_FILE"
fi

if [ ! -d "$ROOT/scripts/venv" ]; then
  step "Creating scripts venv..."
  python3 -m venv "$ROOT/scripts/venv" 2>/dev/null || { python3 -m venv "$ROOT/scripts/venv" 2>&1; exit 1; }
fi
run_silent "Installing Python dependencies..." bash -c "\"$ROOT/scripts/venv/bin/python3\" -m pip install -q \"setuptools<82\" && \"$ROOT/scripts/venv/bin/python3\" -m pip install -q -r \"$ROOT/scripts/requirements.txt\""
step "Setup: node key, guardian details, and Ethereum RPC."
"$ROOT/scripts/venv/bin/python3" "$ROOT/scripts/prompt_and_env.py"

if [ -f "$ENV_FILE" ]; then
  if ! grep -qE "^BASE_DIR=.+" "$ENV_FILE" 2>/dev/null; then
    echo "BASE_DIR=$ROOT" >> "$ENV_FILE"
    step_ok "Added BASE_DIR to .env"
  fi
  if ! grep -qE "^DOCKER_COMPOSE_FILE=.+" "$ENV_FILE" 2>/dev/null; then
    echo "DOCKER_COMPOSE_FILE=$ROOT/docker-compose.yml" >> "$ENV_FILE"
    step_ok "Added DOCKER_COMPOSE_FILE to .env"
  fi
fi

step "Installing control cron..."
"$ROOT/scripts/install-control-cron.sh"

mkdir -p "$ROOT/.data/ethereum-reader" "$ROOT/.data/ethereum-writer" "$ROOT/.data/matic-reader" "$ROOT/.data/signer" "$ROOT/.data/logger" "$ROOT/.data/vm-notifications" "$ROOT/.data/vm-lambda" "$ROOT/.data/vm-twap" "$ROOT/.data/control"

if command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  COMPOSE="docker compose"
fi
step "Starting docker-compose..."
errf=$(mktemp)
if ! $COMPOSE -f "$COMPOSE_FILE" up -d >/dev/null 2>"$errf"; then
  echo -e "${RED}Error: docker-compose up failed.${RST}" >&2
  cat "$errf" >&2
  rm -f "$errf"
  exit 1
fi
rm -f "$errf"

success_msg "Orbs L3 node was installed successfully ! :)"
echo
