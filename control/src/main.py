"""Main entry point of the control"""

import docker
import sys
from config import status_file
from logger import logger
from system_monitor import SystemMonitor
import updater
from updater import get_guardian_node_id
from utils import run_command
from os import getenv

system_monitor = SystemMonitor(client=docker.from_env())

data = {
    "currentVersion": "0.0.0",
    "scheduledVersion": None,
    "updateScheduled": None,
    "updateScheduledFor": None,
}


def main():
    """Main entry point of the control module"""

    cmd = None
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

    logger.info(f"Running control on node [{get_guardian_node_id()}] ...")
    updater.set_error("")

    # TODO - add back when we split into separate repos
    # # Fetch all the tags from the remote repository
    # run_command("git fetch origin --tags")

    # Get the latest tag
    # latest_tag = run_command("git describe --tags $(git rev-list --tags --max-count=1)")

    if cmd == "poll":
        try:
            updater.compare()
        except Exception as e:
            updater.set_error(f"An error occurred while comparing: {e}")

    if cmd is None:
        # hard coded for now
        latest_tag = "0.0.1"

        # update control info
        if latest_tag and latest_tag != data["currentVersion"]:
            # checkout_command = f"git checkout {latest_tag}"
            # run_command(checkout_command)  # checkout the latest tag
            docker_compose_file = getenv("DOCKER_COMPOSE_FILE")

            error = run_command(f"docker-compose -f {docker_compose_file} up -d")
            if error:
                print("Error running docker-compose")

    system_monitor.update()
    system_monitor.persist(status_file)


if __name__ == "__main__":
    main()
