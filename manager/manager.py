import os
import subprocess
import json
from datetime import datetime
from typing import Optional, Tuple

errors_file = '/opt/orbs/errors.txt'
node_version = '/opt/orbs/node-version.json'
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_command(command: str) -> Tuple[Optional[str], Optional[str]]:
    """Runs a shell command and returns the output and error message (if any)

    Args:
        command: The command to run (eg. `docker-compose up -d`)

    Returns:
        A tuple containing the output and error message (if any)
    """
    result = subprocess.run(command, shell=True, capture_output=True)
    
    if result.returncode != 0:
        error_message = result.stderr.decode("utf-8")
        with open(errors_file, "a") as f:
            f.write(f"{timestamp} - {error_message.strip()}\n")
        return None, error_message
    
    output = result.stdout.decode("utf-8")
    return output, None
        

# TODO - add back when we split into seperate repos
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
    _, error = run_command("docker-compose -f /home/ubuntu/deployment/docker-compose.yml up -d")
    if error:
        print("Error running docker-compose")
    
    data["currentVersion"] = latest_tag

# Write the updated data back to the JSON file
with open(node_version, "w") as f:
    json.dump(data, f, indent=4)  # Use indent=4 for pretty-printing
