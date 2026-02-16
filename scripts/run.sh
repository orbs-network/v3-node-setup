#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run this setup with sudo (e.g. sudo ./scripts/run.sh or sudo make setup)." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Checking and installing dependencies..."
"$ROOT/scripts/install-dependencies.sh"

ENV_FILE="$ROOT/.env"
COMPOSE_FILE="$ROOT/docker-compose.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Error: docker-compose.yml not found at $COMPOSE_FILE"
  exit 1
fi

if [ ! -f "$ENV_FILE" ] && [ -f "$ROOT/.env.template" ]; then
  echo "No .env found; copying .env.template to .env"
  cp "$ROOT/.env.template" "$ENV_FILE"
fi

if [ ! -d "$ROOT/scripts/venv" ]; then
  echo "Creating scripts venv..."
  python3 -m venv "$ROOT/scripts/venv"
fi
echo "Installing Python dependencies..."
"$ROOT/scripts/venv/bin/python3" -m pip install -q "setuptools<82"
"$ROOT/scripts/venv/bin/python3" -m pip install -q -r "$ROOT/scripts/requirements.txt"
"$ROOT/scripts/venv/bin/python3" "$ROOT/scripts/prompt_and_env.py"

if [ -f "$ENV_FILE" ]; then
  if ! grep -qE "^BASE_DIR=.+" "$ENV_FILE" 2>/dev/null; then
    echo "BASE_DIR=$ROOT" >> "$ENV_FILE"
    echo "Added BASE_DIR to .env"
  fi
  if ! grep -qE "^DOCKER_COMPOSE_FILE=.+" "$ENV_FILE" 2>/dev/null; then
    echo "DOCKER_COMPOSE_FILE=$ROOT/docker-compose.yml" >> "$ENV_FILE"
    echo "Added DOCKER_COMPOSE_FILE to .env"
  fi
fi

echo "Installing control cron..."
"$ROOT/scripts/install-control-cron.sh"

mkdir -p "$ROOT/.data/ethereum-reader" "$ROOT/.data/ethereum-writer" "$ROOT/.data/matic-reader" "$ROOT/.data/signer" "$ROOT/.data/logger" "$ROOT/.data/vm-notifications" "$ROOT/.data/vm-lambda" "$ROOT/.data/vm-twap" "$ROOT/.data/control"

if command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  COMPOSE="docker compose"
fi
echo "Starting docker-compose..."
$COMPOSE -f "$COMPOSE_FILE" up -d
