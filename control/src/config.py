"""Configuration file for the control service."""

import os

BASE_DIR = os.environ.get("BASE_DIR") or "/opt/orbs"
os.makedirs(f"{BASE_DIR}/control", exist_ok=True)

CONTROL_DIR = os.path.join(BASE_DIR, "control")

status_file = os.path.join(CONTROL_DIR, "status.json")
log_file = os.path.join(CONTROL_DIR, "log.txt")
errors_file = os.path.join(CONTROL_DIR, "errors.txt")
