""" A helper class for getting system metrics and status. """

import json
from datetime import datetime

import docker
import psutil

from logger import logger
from system_monitor_types import Payload, Status


class SystemMonitor:
    """
    A helper class for getting system metrics and status.
    Information tracked includes CPU, memory, disk, process usage and Docker containers.

    Usage:
    - get: Returns the current status of the system
    - update: Updates the status of the system
    - persist_status: Persists the status of the system to a JSON file

    The rest of the methods are protected or private and should not be called directly.
    """

    timestamp: str = ""
    status: str = ""
    error: str = ""
    metrics: dict
    services: dict
    start_time: float

    _client: docker.DockerClient

    def __init__(self, client: docker.DockerClient) -> None:
        logger.info("Initializing SystemMonitor.")

        self.metrics = {}
        self.services = {}
        self.start_time = datetime.now().timestamp()

        self._client = client

    def __str__(self):
        return self.__dump_json()

    def __repr__(self):
        return self.__dump_json()

    def get(self) -> Status:
        """Returns the current status of the system"""

        logger.info("Fetching current system status.")

        return Status(
            Timestamp=self.timestamp,
            Status=self.status,
            Error=self.error,
            Payload=Payload(Metrics=self.metrics, Services=self.services),
        )

    def update(self):
        """Updates the status of the system"""

        logger.info("Updating system metrics and services info")

        now = datetime.now()
        metrics = self._get_metrics(now)

        self.timestamp = now.isoformat()
        self.status = f"RAM = {round(metrics['MemoryUsedMBytes'], 2)}mb, CPU = {metrics['CPULoadPercent']}%"
        # TODO: What exactly is an error in this context?
        self.error = ""

        self.metrics = metrics
        self.services = self._get_docker_service_info()

    def persist(self, status_file_path: str):
        """Persists the status of the system to a file"""

        logger.info("Persisting system status to file: %s", status_file_path)

        with open(status_file_path, "w", encoding="utf8") as file:
            json.dump(self.get(), file, indent=4)

    def _get_metrics(self, now: datetime) -> dict:
        """Returns a dictionary of system metrics (CPU, memory, disk, etc)"""

        logger.info("Fetching system metrics.")

        # Get uptime by subtracting the boot time from the current time
        boot_time = now.timestamp() - psutil.boot_time()
        uptime = now.timestamp() - self.start_time

        # Get the CPU load for the last minute.
        # The psutil.cpu_percent() function returns the CPU usage as a percentage since the last call,
        # so we need to call it twice with a delay to get the average CPU usage over a period of time.
        cpu_load_percent = psutil.cpu_percent(interval=None)

        # Get memory usage details
        memory_info = psutil.virtual_memory()
        memory_used_percent = memory_info.percent
        memory_used_mbytes = self.__convert_bytes_to_mbytes(memory_info.used)
        memory_total_mbytes = self.__convert_bytes_to_mbytes(memory_info.total)

        metrics = {
            "Uptime": uptime,
            "BootTime": boot_time,
            "CPULoadPercent": cpu_load_percent,
            "MemoryUsedPercent": memory_used_percent,
            "MemoryUsedMBytes": memory_used_mbytes,
            "MemoryTotalMBytes": memory_total_mbytes,
            "Disks": self._get_disk_info(),
            "Processes": self._get_process_info(),
        }

        return metrics

    def _get_disk_info(self) -> list[dict]:
        """Returns a list of disk usage information"""

        logger.info("Fetching disk usage information.")

        disk_info = []

        for partition in psutil.disk_partitions():
            usage = psutil.disk_usage(partition.mountpoint)
            partition = {
                "Mountpoint": partition.mountpoint,
                "TotalMbytes": self.__convert_bytes_to_mbytes(usage.total),
                "UsedMbytes": self.__convert_bytes_to_mbytes(usage.used),
                "UsedPercent": usage.percent,
            }
            disk_info.append(partition)

        return disk_info

    def _get_process_info(self) -> list[dict]:
        """Returns a list of system processes and their memory usage"""

        logger.info("Fetching system process information.")

        process_info = []

        for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
            if proc.ppid() == 1:  # Only include parent processes
                memory_used_mb = ""
                if proc.info["memory_info"] is not None:
                    memory_used_mb = self.__convert_bytes_to_mbytes(
                        proc.info["memory_info"].rss
                    )

                cmd_line = ""
                if proc.info["cmdline"] is not None:
                    cmd_line = " ".join(proc.info["cmdline"])
                    cmd_line = (
                        (cmd_line[:75] + "...") if len(cmd_line) > 75 else cmd_line
                    )

                process_data = {
                    "Name": proc.info["name"],
                    "Command": cmd_line,
                    "MemoryUsedMbytes": memory_used_mb,
                    "PID": proc.info["pid"],
                    "ParentPID": proc.ppid(),  # Get parent PID
                }

                process_info.append(process_data)

        return process_info

    def _get_docker_service_info(self) -> list[dict]:
        """Returns a list of running Docker containers and their details"""

        logger.info("Fetching Docker container information.")

        service_info = []

        for container in self._client.containers.list():
            container_attrs = container.attrs
            image = container_attrs.get("Image")
            if image is None:
                image = "(None)"

            service_data = {
                "Name": container.name,
                "Image": image,
                "Command": " ".join(container.attrs["Config"]["Cmd"]),
                "Environment": self.__get_filtered_env_vars(
                    container.attrs["Config"]["Env"]
                ),
                "CreatedAt": container_attrs["Created"],
                "ExitedAt": container_attrs["State"]["FinishedAt"],
                "Status": container_attrs["State"]["Status"],
                "Running": container_attrs["State"]["Running"],
                "Paused": container_attrs["State"]["Paused"],
                "Restarting": container_attrs["State"]["Restarting"],
                "OOMKilled": container_attrs["State"]["OOMKilled"],
                "Dead": container_attrs["State"]["Dead"],
                "Pid": container_attrs["State"]["Pid"],
                "ExitCode": container_attrs["State"]["ExitCode"],
                "Error": container_attrs["State"]["Error"],
            }

            service_info.append(service_data)

        return service_info

    def __is_not_blacklisted(self, env_var: str) -> bool:
        """Returns True if the environment variable is not blacklisted"""
        return not any(
            blacklisted in env_var
            for blacklisted in ["ETHEREUM_ENDPOINT", "KEY", "SECRET", "PRIVATE_KEY"]
        )

    def __get_filtered_env_vars(self, env_vars: list[str]) -> list[str]:
        """Returns a list of environment variables with sensitive information removed"""
        return list(filter(self.__is_not_blacklisted, env_vars))

    def __convert_bytes_to_mbytes(self, _bytes: int) -> float:
        """Converts bytes to megabytes"""
        return round(_bytes / 1024 / 1024, 6)

    def __dump_json(self):
        """Returns a pretty-printed string representation of the status object"""
        return json.dumps(self.get(), indent=4)
