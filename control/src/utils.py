"""
Various helper functions used in the node control
"""

import select
import subprocess
from typing import Optional

from logger import logger


class CommandError(RuntimeError):
    """Raised when a command exits with a non-zero status."""

    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output
        super().__init__(f"Command '{' '.join(command)}' exited with status {returncode}: {output}")


def run(command: list[str], check: bool = True) -> str:
    """Runs a command, logging both of its output streams.

    Args:
        command: The command and its arguments (eg. `["docker", "compose", "up", "-d"]`).
        check: Whether to raise `CommandError` when the command exits non-zero.

    Returns:
        The command's stdout, stripped.

    Raises:
        CommandError: If the command exits non-zero and `check` is set.
    """

    logger.debug("Running command: %s", " ".join(command))

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if stdout:
        logger.info(stdout)

    # docker compose reports its normal progress on stderr, so output there does not mean
    # the command failed - only the exit status tells us that.
    if stderr:
        (logger.error if result.returncode != 0 else logger.info)(stderr)

    if result.returncode != 0:
        error = CommandError(command, result.returncode, stderr or stdout)
        logger.error(str(error))

        if check:
            raise error

    return stdout


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
