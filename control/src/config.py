"""Configuration file for the control service."""

import os

BASE_DIR = os.environ.get("BASE_DIR") or "/opt/orbs"
CONTROL_DIR = os.path.join(BASE_DIR, ".data", "control")
os.makedirs(CONTROL_DIR, exist_ok=True)

# The updater is a module inside control rather than a process of its own, but "did the
# last update work" is a different question from "is control alive", so it gets its own
# log. The logger serves it from here, which is why it is a sibling of the other
# components' directories rather than something under control's.
UPDATER_DIR = os.path.join(BASE_DIR, ".data", "updater")
os.makedirs(UPDATER_DIR, exist_ok=True)

status_file = os.path.join(CONTROL_DIR, "status.json")
log_file = os.path.join(CONTROL_DIR, "log.txt")
errors_file = os.path.join(CONTROL_DIR, "errors.txt")

updater_log_file = os.path.join(UPDATER_DIR, "log.txt")

# Survives the per-tick process boundary. Control is a fresh process every minute, so
# anything that has to be counted across ticks - how many times an update has failed in a
# row, most of all - cannot live in memory.
update_state_file = os.path.join(CONTROL_DIR, "update_state.json")

# Written by run-control.sh, which is the only thing that can see a skipped tick: control
# runs only while holding the lock, so from the inside it is always held by itself.
poll_state_file = os.path.join(CONTROL_DIR, "poll.state")
poll_kills_file = os.path.join(CONTROL_DIR, "poll.kills")
