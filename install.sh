#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RST='\033[0m'
step() { echo -e "${BLUE}[*]${RST} $*"; }
err() { echo -e "${RED}Error:${RST} $*" >&2; exit 1; }

if [ "$EUID" -ne 0 ]; then
  err "Please run with sudo (e.g. sudo ./install.sh or curl -sSL ... | sudo bash)."
fi

case "$(uname -s)" in
  Darwin) ;;
  Linux)
    if [ -f /etc/os-release ]; then
      # shellcheck source=/dev/null
      . /etc/os-release
      if [ "${ID:-}" != "ubuntu" ]; then
        err "Unsupported OS: this installer supports macOS and Ubuntu Linux only (detected: ${ID:-unknown})."
      fi
    else
      err "Unsupported OS: this installer supports macOS and Ubuntu Linux only. Could not detect distribution."
    fi
    ;;
  *)
    err "Unsupported OS: $(uname -s). This installer supports macOS and Ubuntu Linux only."
    ;;
esac

echo -e "${BLUE}"
cat << 'ORBS_ASCII'
▄████▄ ▄▄▄▄  ▄▄▄▄   ▄▄▄▄   ██     ████▄   ███  ██  ▄▄▄  ▄▄▄▄  ▄▄▄▄▄
██  ██ ██▄█▄ ██▄██ ███▄▄   ██      ▄▄██   ██ ▀▄██ ██▀██ ██▀██ ██▄▄
▀████▀ ██ ██ ██▄█▀ ▄▄██▀   ██████ ▄▄▄█▀   ██   ██ ▀███▀ ████▀ ██▄▄▄
ORBS_ASCII
echo -e "${RST}"

INSTALL_DIR="${INSTALL_DIR:-/opt/orbs/v3-node-setup}"
REPO_URL="${REPO_URL:-https://github.com/orbs-network/v3-node-setup.git}"
BRANCH="${BRANCH:-main}"

if ! command -v git &>/dev/null; then
  step "Installing git..."
  if [ -f /etc/debian_version ] || [ -f /etc/apt/sources.list ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || { apt-get update 2>&1; exit 1; }
    apt-get install -y -qq git >/dev/null 2>&1 || { apt-get install -y git 2>&1; exit 1; }
  else
    err "git is required. Please install git and re-run."
  fi
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  step "Updating existing clone at $INSTALL_DIR..."
  errf=$(mktemp)
  if ! git -C "$INSTALL_DIR" fetch origin >/dev/null 2>"$errf"; then cat "$errf" >&2; rm -f "$errf"; exit 1; fi
  git -C "$INSTALL_DIR" checkout -q "$BRANCH" 2>/dev/null || true
  if ! git -C "$INSTALL_DIR" pull -q origin "$BRANCH" >/dev/null 2>"$errf"; then echo -e "${RED}Error: git pull failed.${RST}" >&2; cat "$errf" >&2; rm -f "$errf"; exit 1; fi
  rm -f "$errf"
else
  step "Cloning to $INSTALL_DIR..."
  mkdir -p "$(dirname "$INSTALL_DIR")"
  errf=$(mktemp)
  if ! git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>"$errf"; then echo -e "${RED}Error: git clone failed.${RST}" >&2; cat "$errf" >&2; rm -f "$errf"; exit 1; fi
  rm -f "$errf"
fi

commit=$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || true)
tag=$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || git -C "$INSTALL_DIR" describe --tags 2>/dev/null || true)
branch_info="Using branch: $BRANCH"
[ -n "$commit" ] && branch_info="$branch_info (commit: $commit)"
[ -n "$tag" ] && branch_info="$branch_info (tag: $tag)"
step "$branch_info"

SETUP_SCRIPT="$INSTALL_DIR/scripts/run.sh"
if [ ! -f "$SETUP_SCRIPT" ]; then
  err "Setup script not found at $SETUP_SCRIPT"
fi

step "Running setup..."
exec "$SETUP_SCRIPT"
