""" Configuration file for the manager service. """

import os

BASE_DIR = os.environ.get("BASE_DIR") or "/opt/orbs"
os.makedirs(f"{BASE_DIR}/manager", exist_ok=True)

MANAGER_DIR = os.path.join(BASE_DIR, "manager")

status_file = os.path.join(MANAGER_DIR, "status.json")
log_file = os.path.join(MANAGER_DIR, "log.txt")
errors_file = os.path.join(MANAGER_DIR, "errors.txt")
