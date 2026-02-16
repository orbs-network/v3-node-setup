"""Configuration file for the control service."""

import os

BASE_DIR = os.environ.get("BASE_DIR") or "/opt/orbs"
CONTROL_DIR = os.path.join(BASE_DIR, ".data", "control")
os.makedirs(CONTROL_DIR, exist_ok=True)

status_file = os.path.join(CONTROL_DIR, "status.json")
log_file = os.path.join(CONTROL_DIR, "log.txt")
errors_file = os.path.join(CONTROL_DIR, "errors.txt")
