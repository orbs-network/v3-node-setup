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
REQUIREMENTS="$ROOT/control/requirements.txt"
# Kept inside the venv, so recreating the venv forgets it, which is what we want.
REQUIREMENTS_MARKER="$VENV/.requirements.sha256"

checksum() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

if [ ! -d "$VENV" ]; then
  echo "Creating control venv..."
  python3 -m venv "$VENV"
fi

# Install when the venv is new or requirements.txt changed since the last successful
# install. Installing only on venv creation meant a new dependency never reached an
# existing node, and control would then fail to import it once a minute, forever.
want_requirements="$(checksum "$REQUIREMENTS")"
have_requirements="$(cat "$REQUIREMENTS_MARKER" 2>/dev/null || true)"

if [ "$want_requirements" != "$have_requirements" ]; then
  echo "Installing control dependencies..."
  if ! "$VENV/bin/python3" -m pip install -q -r "$REQUIREMENTS"; then
    echo "Error: pip install failed for $REQUIREMENTS" >&2
    exit 1
  fi
  # Only recorded after a successful install, so a failure is retried next run.
  echo "$want_requirements" > "$REQUIREMENTS_MARKER"
fi

"$VENV/bin/python3" "$ROOT/control/src/main.py" "$@"
