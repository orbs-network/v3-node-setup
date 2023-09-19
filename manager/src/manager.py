""" Main entry point of the manager """

import docker

from config import status_file
from logger import logger
from system_monitor import SystemMonitor
from utils import run_command

system_monitor = SystemMonitor(client=docker.from_env())

data = {
    "currentVersion": "0.0.0",
    "scheduledVersion": None,
    "updateScheduled": None,
    "updateScheduledFor": None,
}


def main():
    """Main entry point of the manager"""

    logger.info("Running manager...")

    # TODO - add back when we split into separate repos
    # # Fetch all the tags from the remote repository
    # run_command("git fetch origin --tags")

    # Get the latest tag
    # latest_tag = run_command("git describe --tags $(git rev-list --tags --max-count=1)")

    # hard coded for now
    latest_tag = "0.0.1"

    # upddate manager info
    if latest_tag and latest_tag != data["currentVersion"]:
        # checkout_command = f"git checkout {latest_tag}"
        # run_command(checkout_command)  # checkout the latest tag
        error = run_command(
            "docker-compose -f $HOME/deployment/docker-compose.yml up -d"
        )
        if error:
            print("Error running docker-compose")

    system_monitor.update()
    system_monitor.persist(status_file)


if __name__ == "__main__":
    main()
