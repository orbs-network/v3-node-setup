GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RST='\033[0m'

step() { echo -e "${BLUE}[*]${RST} $*"; }
step_ok() { echo -e "${GREEN}[*]${RST} $*"; }
err() { echo -e "${RED}Error:${RST} $*" >&2; exit 1; }
success_msg() { echo -e "${YELLOW}$*${RST}"; }

run_silent() {
  local desc="$1"
  shift
  step "$desc"
  local errf
  errf=$(mktemp)
  if "$@" >/dev/null 2>"$errf"; then
    rm -f "$errf"
    return 0
  fi
  echo -e "${RED}Error: $desc failed.${RST}" >&2
  cat "$errf" >&2
  rm -f "$errf"
  exit 1
}
