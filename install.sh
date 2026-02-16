#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run with sudo (e.g. sudo ./install.sh or curl -sSL ... | sudo bash)." >&2
  exit 1
fi

INSTALL_DIR="${INSTALL_DIR:-/opt/orbs/v3-node-setup}"
REPO_URL="${REPO_URL:-https://github.com/orbs-network/v3-node-setup.git}"
BRANCH="${BRANCH:-main}"

echo "Using branch: $BRANCH"

if ! command -v git &>/dev/null; then
  echo "Installing git..."
  if [ -f /etc/debian_version ] || [ -f /etc/apt/sources.list ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq git
  else
    echo "Error: git is required. Please install git and re-run." >&2
    exit 1
  fi
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing clone at $INSTALL_DIR..."
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" checkout -q "$BRANCH" 2>/dev/null || true
  git -C "$INSTALL_DIR" pull -q origin "$BRANCH"
else
  echo "Cloning to $INSTALL_DIR..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

SETUP_SCRIPT="$INSTALL_DIR/scripts/run.sh"
if [ ! -f "$SETUP_SCRIPT" ]; then
  echo "Error: Setup script not found at $SETUP_SCRIPT" >&2
  exit 1
fi

echo "Running setup..."
exec "$SETUP_SCRIPT"
