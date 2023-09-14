"""
Various helper functions used in the node manager
"""


import select
import subprocess
from typing import Optional

from logger import logger


def run_command(command: str) -> Optional[str]:
    """Runs a shell command and returns the error message (if any).

    Args:
        command: The command to run (eg. `docker-compose up -d`).

    Returns:
        The error message (if any).
    """

    logger.info("Running command: %s", command)

    with subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    ) as process:
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
                logger.info("Command '%s' has finished.", command)
                # Process has finished, read rest of the output
                for output in [process.stdout, process.stderr]:
                    for line in output.readlines():
                        line = line.strip()
                        if line:
                            logger.info(line)

                if process.returncode != 0:
                    error_message = f"Command '{command}' returned non-zero exit status {process.returncode}"
                    logger.error(error_message)
                    return error_message

                return None
