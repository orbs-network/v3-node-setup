import os
import json
import select
import subprocess
from datetime import datetime
from typing import Optional
from status import Status

base_dir = "/opt/orbs"
os.makedirs(f"{base_dir}/manager", exist_ok=True)
errors_file = f"{base_dir}/manager/errors.txt"
status_file = f"{base_dir}/manager/status.json"
log_file = f"{base_dir}/manager/log.txt"

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# status object
status = Status()

data = {
    "currentVersion": "0.0.0",
    "scheduledVersion": None,
    "updateScheduled": None,
    "updateScheduledFor": None,
}


# logger
def append_line_to(file_name, line):
    print(line)
    timestamp = datetime.now().isoformat()

    # Check if file exists, if not create it
    if not os.path.isfile(file_name):
        with open(file_name, "w") as file:
            file.write(f"{timestamp}: {line}\n")
    else:
        # File exists, append line to it
        with open(file_name, "a") as file:
            file.write(f"{timestamp}: {line}\n")


# write log
append_line_to(log_file, "manager.py triggered")


def run_command(command: str) -> Optional[str]:
    append_line_to(log_file, "run_command:")
    append_line_to(log_file, command)

    """Runs a shell command and returns the error message (if any).

    Args:
        command: The command to run (eg. `docker-compose up -d`).

    Returns:
        The error message (if any).
    """
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    while True:
        # Use select for non-blocking I/O on both stdout and stderr
        ready_to_read, _, _ = select.select([process.stdout, process.stderr], [], [])
        for output in ready_to_read:
            line = output.readline().strip()

            # Print output in real-time
            if line:
                print(line)

        # Check for termination
        if process.poll() is not None:
            append_line_to(log_file, "poll for process for stdout")
            # Process has finished, read rest of the output
            for output in [process.stdout, process.stderr]:
                for line in output.readlines():
                    line = line.strip()
                    if line:
                        append_line_to(log_file, line)

            if process.returncode != 0:
                error_message = f"Command '{command}' returned non-zero exit status {process.returncode}"
                append_line_to(errors_file, error_message)
                return error_message

            return None


# TODO - add back when we split into separate repos
# # Fetch all the tags from the remote repository
# run_command("git fetch origin --tags")

# Get the latest tag
# latest_tag = run_command("git describe --tags $(git rev-list --tags --max-count=1)")


# updated data & metrics
status.update()

# hard coded for now
latest_tag = "0.0.1"

# upddate manager info
if latest_tag and latest_tag != data["currentVersion"]:
    # checkout_command = f"git checkout {latest_tag}"
    # run_command(checkout_command)  # checkout the latest tag
    error = run_command("docker-compose -f $HOME/deployment/docker-compose.yml up -d")
    if error:
        print("Error running docker-compose")

    data["currentVersion"] = latest_tag


with open(status_file, "w") as f:
    obj = status.get()
    obj["Payload"]["Manager"] = data
    json.dump(obj, f, indent=4)  # Use indent=4 for pretty-printing
