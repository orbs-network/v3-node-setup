#!/usr/bin/env bash
set -e

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

err() {
  echo "Error: $1" >&2
  exit 1
}

check_docker() {
  if command -v docker &>/dev/null; then
    return 0
  fi
  return 1
}

check_compose() {
  if command -v docker-compose &>/dev/null; then
    return 0
  fi
  if docker compose version &>/dev/null 2>&1; then
    return 0
  fi
  return 1
}

check_python() {
  if ! command -v python3 &>/dev/null; then
    return 1
  fi
  local ver
  ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null) || return 1
  local major minor
  major=${ver%%.*}
  minor=${ver#*.}
  minor=${minor%%.*}
  if [ "$major" -lt "$MIN_PYTHON_MAJOR" ] || { [ "$major" -eq "$MIN_PYTHON_MAJOR" ] && [ "$minor" -lt "$MIN_PYTHON_MINOR" ]; }; then
    return 1
  fi
  return 0
}

check_venv() {
  python3 -c "import venv" 2>/dev/null
}

check_pip() {
  python3 -m pip --version &>/dev/null
}

ensure_linux_build_deps() {
  if [ ! -f /etc/debian_version ] && [ ! -f /etc/apt/sources.list ]; then
    return 0
  fi
  export DEBIAN_FRONTEND=noninteractive
  echo "Ensuring build dependencies for Python packages (e.g. coincurve)..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq build-essential autoconf automake libtool pkg-config 2>/dev/null || sudo apt-get install -y build-essential autoconf automake libtool pkg-config
}

install_linux() {
  local need_docker=false need_compose=false need_python=false
  check_docker || need_docker=true
  check_compose || need_compose=true
  check_python || need_python=true
  check_venv || need_python=true
  check_pip || need_python=true

  if [ "$need_docker" = false ] && [ "$need_compose" = false ] && [ "$need_python" = false ]; then
    return 0
  fi

  if [ -f /etc/debian_version ] || [ -f /etc/apt/sources.list ]; then
    export DEBIAN_FRONTEND=noninteractive
    sudo apt-get update -qq

    if [ "$need_docker" = true ] || [ "$need_compose" = true ]; then
      echo "Installing Docker..."
      curl -fsSL https://get.docker.com | sh
      sudo usermod -aG docker "${USER:-$(whoami)}" 2>/dev/null || true
      if ! check_compose; then
        echo "Installing docker-compose standalone..."
        arch=$(uname -m)
        [ "$arch" = x86_64 ] && arch=linux-x86_64 || arch=linux-aarch64
        sudo curl -sSL "https://github.com/docker/compose/releases/download/v2.30.2/docker-compose-$arch" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
      fi
    fi

    if [ "$need_python" = true ]; then
      echo "Installing Python and pip..."
      sudo apt-get install -y -qq python3 python3-venv python3-pip 2>/dev/null || sudo apt-get install -y python3 python3-venv python3-pip
    fi
  else
    err "Unsupported Linux distro for auto-install. Please install manually: docker, docker-compose, python3 (${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+), python3-venv, pip."
  fi
}

run_mac() {
  local missing=()
  if ! check_docker; then
    missing+=(docker)
  fi
  if ! check_compose; then
    missing+=(docker-compose)
  fi
  if ! check_python; then
    missing+=(python3)
  fi
  if ! check_venv; then
    missing+=(python3-venv)
  fi
  if ! check_pip; then
    missing+=(pip)
  fi

  if [ ${#missing[@]} -eq 0 ]; then
    echo "All dependencies satisfied."
    return 0
  fi

  echo "Missing required dependencies: ${missing[*]}" >&2
  echo "On macOS please install them manually (e.g. Homebrew: brew install docker python@3.11)." >&2
  exit 1
}

run_linux() {
  ensure_linux_build_deps
  install_linux
  if ! check_docker; then
    err "Docker could not be installed or is not in PATH. Log out and back in after install, then re-run."
  fi
  if ! check_compose; then
    err "Docker Compose could not be installed or is not in PATH."
  fi
  if ! check_python; then
    err "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ required."
  fi
  if ! check_venv; then
    err "python3-venv could not be installed."
  fi
  if ! check_pip; then
    err "pip could not be installed."
  fi
  echo "Dependencies OK."
}

case "$(uname -s)" in
  Darwin)
    run_mac
    ;;
  Linux)
    run_linux
    ;;
  *)
    err "Unsupported OS: $(uname -s). Only macOS and Linux are supported."
    ;;
esac
