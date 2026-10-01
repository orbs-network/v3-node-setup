#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PATH="/usr/local/bin:/usr/bin:/bin${PATH:+:$PATH}"

# Run the poll in its own process group, so a stuck one can be stopped as a group. Killing
# only this script would orphan the docker compose child it is waiting on, which would
# carry on changing state while the next tick started a second update - the very pile-up
# the lock exists to prevent (#82). setsid makes this process a group leader, so from here
# on its pid is also its process group id, which is what the holder file records.
#
# Skipped when stdout is a terminal, so an interactive `make control` still answers Ctrl-C,
# and when setsid is missing, as on a dev Mac. The crontab is written once at install time
# and never updated afterwards, so this has to live here rather than in the cron entry.
#
# -w so this process waits for the real run and exits with its status. Without it setsid
# forks and returns immediately, and cron would record every poll as finishing instantly
# however long it actually ran.
if [ -z "${CONTROL_SETSID:-}" ] && [ ! -t 1 ] && command -v setsid >/dev/null 2>&1; then
  export CONTROL_SETSID=1
  exec setsid -w "$0" "$@"
fi

set -a
[ -f "$ROOT/.env" ] && . "$ROOT/.env"
set +a

export BASE_DIR="$ROOT"
export DOCKER_COMPOSE_FILE="$ROOT/docker-compose.yml"

# Holds the log, the poll lock and the lock holder. The cron installer creates it, but a
# run from the Makefile on a fresh checkout would not have been through that.
CONTROL_DIR="$ROOT/.data/control"
mkdir -p "$CONTROL_DIR"

# The cron entry appends this script's output to the control log, and it runs every
# minute forever, so without a cap the file grows until someone notices. It reached 969MB
# on a node before this existed.
#
# Rotating by moving the file is safe here because cron opens it fresh on each run, so
# nothing holds a descriptor across polls. The current run's own output still goes to the
# file it inherited, which is now the rotated one - harmless, and it avoids the sparse
# file that truncating an open log would leave behind.
LOG_FILE="$CONTROL_DIR/log.txt"
LOG_MAX_BYTES="${LOG_MAX_BYTES:-10485760}"
LOG_KEEP="${LOG_KEEP:-3}"

# Everything this script says goes to stdout, which the crontab entry appends to
# $LOG_FILE, so these lines sit in the same file as control's own. The shape matches
# control/src/logger.py's formatter, so a tick that only skips is still timestamped.
log() {
  printf '%s - run-control.sh - INFO - %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

rotate_log() {
  [ -f "$LOG_FILE" ] || return 0

  size="$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)"
  [ "$size" -lt "$LOG_MAX_BYTES" ] && return 0

  i="$LOG_KEEP"
  while [ "$i" -gt 1 ]; do
    prev="$((i - 1))"
    [ -f "$LOG_FILE.$prev" ] && mv -f "$LOG_FILE.$prev" "$LOG_FILE.$i"
    i="$prev"
  done

  mv -f "$LOG_FILE" "$LOG_FILE.1"
  : > "$LOG_FILE"
}

rotate_log

# Only one poll at a time. cron fires every 60 seconds and an update that builds images
# from source has been measured at 57 of them, so without a lock the next tick starts a
# second git checkout -f, docker compose build and up -d in the same working tree while
# the first is still mid-flight (#82).
#
# -n, never blocking: a tick that cannot take the lock skips entirely. Blocking would
# park a process per minute behind a stuck update and we would end up with the pile-up
# the lock exists to prevent. Skipping costs nothing - compare() is idempotent and the
# next tick is a minute away.
#
# The flock itself is released by the kernel when this process exits, however it exits,
# so there is no such thing as a stale lock to clear here. The holder file below is
# separate from the lock file on purpose: writing into the fd flock holds would mean
# truncating it under the kernel.
LOCK_FILE="$CONTROL_DIR/poll.lock"
HOLDER_FILE="$CONTROL_DIR/poll.holder"

# A poll held this long is treated as wedged rather than slow. Generous on purpose: a cold
# image pull plus a cold build from source runs to a few minutes, and killing something
# that was going to finish is worse than waiting.
POLL_KILL_AFTER_SECONDS="${POLL_KILL_AFTER_SECONDS:-1200}"

# After this many kills we stop killing and only report. Without a cap, an update that is
# slow rather than stuck - a large image over a bad link - would be killed at the limit,
# restarted, killed again, forever: a node that never updates and never says why. The
# count is reset by a poll that runs to completion, not by merely taking the lock, since
# after a kill the next tick does take the lock and the cap would never be reached.
POLL_KILL_CAP="${POLL_KILL_CAP:-3}"
KILL_COUNT_FILE="$CONTROL_DIR/poll.kills"

# Field 22 of /proc/<pid>/stat is the process start time in clock ticks. It is read from
# after the comm field, which is parenthesised and may contain spaces, so counting fields
# from the left of the line is not safe.
proc_starttime() {
  local stat after
  stat="$(cat "/proc/$1/stat" 2>/dev/null)" || return 1
  after="${stat##*') '}"
  [ "$after" != "$stat" ] || return 1
  printf '%s' "$after" | awk 'NF >= 20 { print $20 }'
}

# 90061 -> 1h1m, 240 -> 4m, 12 -> 12s.
human_duration() {
  local secs="$1" mins hours
  if [ "$secs" -lt 60 ]; then
    printf '%ds' "$secs"
    return 0
  fi
  mins="$((secs / 60))"
  if [ "$mins" -lt 60 ]; then
    printf '%dm' "$mins"
    return 0
  fi
  hours="$((mins / 60))"
  printf '%dh%dm' "$hours" "$((mins % 60))"
}

# Say who holds the lock and for how long. A lock held for many minutes is itself worth
# knowing about, and an unreadable holder file is reported as exactly that rather than
# guessed at - it happens in the sliver between a holder taking the lock and writing the
# file, and unknown never means OK.
report_held_lock() {
  local line pid starttime age kills now_starttime waited

  line=""
  [ -s "$HOLDER_FILE" ] && line="$(head -n 1 "$HOLDER_FILE" 2>/dev/null || true)"
  pid="${line%% *}"
  starttime="${line##* }"

  if [ -z "$pid" ] || ! [[ "$pid" =~ ^[0-9]+$ ]]; then
    log "Poll still running but its holder file is missing or unreadable ($HOLDER_FILE) - skipping this tick"
    return 0
  fi

  # etimes is the kernel's own age for the process in seconds, so it is unaffected by
  # clock changes - which a timestamp we wrote ourselves would not be.
  age="$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d '[:space:]' || true)"

  if ! [[ "$age" =~ ^[0-9]+$ ]]; then
    log "Poll still running (pid $pid, age unknown) - skipping this tick"
    return 0
  fi

  if [ "$age" -lt "$POLL_KILL_AFTER_SECONDS" ]; then
    log "Poll still running (pid $pid, held $(human_duration "$age")) - will be killed past $(human_duration "$POLL_KILL_AFTER_SECONDS") - skipping this tick"
    return 0
  fi

  kills="$(cat "$KILL_COUNT_FILE" 2>/dev/null || true)"
  [[ "$kills" =~ ^[0-9]+$ ]] || kills=0

  if [ "$kills" -ge "$POLL_KILL_CAP" ]; then
    log "Poll held $(human_duration "$age") and already killed $kills times - NOT killing again, this node needs a human"
    return 0
  fi

  # The start time recorded when the lock was taken pins the process beyond PID reuse. If
  # it no longer matches, the holder we recorded is gone and something else is sitting on
  # the lock - an orphaned child that outlived its parent, most likely. Signalling a
  # recycled pid's process group as root is exactly the mistake worth never making, so
  # report and leave it alone.
  now_starttime="$(proc_starttime "$pid" 2>/dev/null || true)"

  if [ -z "$now_starttime" ] || [ "$now_starttime" != "$starttime" ]; then
    log "Lock is held but pid $pid is not the process that took it - not signalling anything, this node needs a human"
    return 0
  fi

  log "Poll held $(human_duration "$age"), past the $(human_duration "$POLL_KILL_AFTER_SECONDS") limit - killing process group $pid (kill $((kills + 1)) of $POLL_KILL_CAP)"

  # Recorded before signalling, so a kill that takes the node down with it still counts.
  echo "$((kills + 1))" > "$KILL_COUNT_FILE"

  # The whole group, so the docker child goes with its parent. TERM first, to give docker
  # a chance to tidy up, and only then KILL.
  kill -TERM "-$pid" 2>/dev/null || true

  waited=0
  while [ "$waited" -lt 30 ] && kill -0 "$pid" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
  done

  if kill -0 "$pid" 2>/dev/null; then
    log "Process group $pid ignored SIGTERM after 30s - sending SIGKILL"
    kill -KILL "-$pid" 2>/dev/null || true
  else
    log "Process group $pid stopped after $(human_duration "$waited")"
  fi
}

if command -v flock >/dev/null 2>&1; then
  # Appended to rather than truncated, so the open never disturbs a lock another process
  # is holding on the same file.
  exec 9>>"$LOCK_FILE"

  if flock -n 9; then
    # Written only once the lock is ours, so a reader either sees a holder that really
    # does hold it or sees nothing at all. The start time pins the identity of the
    # process beyond PID reuse, which is what a later phase needs before it could signal
    # anything; phase 1 only ever reads this file to report.
    starttime="$(proc_starttime "$$" || true)"
    printf '%s %s\n' "$$" "${starttime:-unknown}" > "$HOLDER_FILE"
    trap 'rm -f "$HOLDER_FILE"' EXIT

    # A kill during `git checkout` leaves .git/index.lock behind, and every later update
    # then fails on it until someone removes it by hand - trading a stuck node for a
    # permanently broken one. We hold the poll lock here, so no other control run exists
    # and any index.lock is a leftover rather than a live operation.
    if [ -f "$ROOT/.git/index.lock" ]; then
      log "Removing a leftover .git/index.lock - a previous run did not finish cleanly"
      rm -f "$ROOT/.git/index.lock"
    fi
  else
    report_held_lock
    exit 0
  fi
else
  # The nodes are Ubuntu and always have flock. This keeps `make control-poll` working on
  # a dev machine that does not, where there is no cron tick to collide with anyway.
  log "flock is not available - running this poll without the lock"
fi

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

status=0
"$VENV/bin/python3" "$ROOT/control/src/main.py" "$@" || status=$?

# Reaching here means this poll ran to completion rather than being killed, which is the
# evidence that the node is not wedged, so the kill budget is restored. Control's own exit
# status is deliberately not part of that: a poll that ran and reported a failure still
# ran. Resetting on taking the lock instead would defeat the cap entirely, since the tick
# after a kill does take the lock.
rm -f "$KILL_COUNT_FILE"

exit "$status"
