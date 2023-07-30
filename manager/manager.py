import json
import select
import subprocess
from datetime import datetime
from typing import Optional

errors_file = '/opt/orbs/errors.txt'
node_version = '/opt/orbs/node-version.json'
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_command(command: str) -> Optional[str]:
    """Runs a shell command and returns the error message (if any).

    Args:
        command: The command to run (eg. `docker-compose up -d`).

    Returns:
        The error message (if any).
    """
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

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
            # Process has finished, read rest of the output 
            for output in [process.stdout, process.stderr]:
                for line in output.readlines():
                    line = line.strip()
                    if line:
                        print(line)

            if process.returncode != 0:
                with open(errors_file, "a") as f:
                    error_message = f"Command '{command}' returned non-zero exit status {process.returncode}"
                    f.write(f"{timestamp} - {error_message}\n")
                return error_message
            
            return None
        

# TODO - add back when we split into separate repos
# # Fetch all the tags from the remote repository
# run_command("git fetch origin --tags")

# # Get the latest tag
# latest_tag = run_command("git describe --tags $(git rev-list --tags --max-count=1)")

latest_tag = "0.0.1"

# Load the existing data from the JSON file
with open(node_version, "r") as f:
    data = json.load(f)

# Update the fields in the JSON file
data["lastUpdated"] = timestamp

if latest_tag and latest_tag != data["currentVersion"]:
    # checkout_command = f"git checkout {latest_tag}"
    # run_command(checkout_command)  # checkout the latest tag
    error = run_command("docker-compose -f $HOME/deployment/docker-compose.yml up -d")
    if error:
        print("Error running docker-compose")
    
    data["currentVersion"] = latest_tag

# Write the updated data back to the JSON file
with open(node_version, "w") as f:
    json.dump(data, f, indent=4)  # Use indent=4 for pretty-printing
