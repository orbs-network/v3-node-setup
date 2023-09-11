import psutil
import docker
from datetime import datetime


class Status:
    def __init__(self):
        self.startTime = datetime.now().timestamp()

    def update(self):
        now = datetime.now()
        self.timestamp = now.isoformat()
        self.error = ""

        self.payload = {"Metrics": {}}

        # Get uptime by subtracting the boot time from the current time
        boot_time = now.timestamp() - psutil.boot_time()
        uptime = now.timestamp() - self.startTime

        # Get the CPU load for the last minute.
        # The psutil.cpu_percent() function returns the CPU usage as a percentage since the last call,
        # so we need to call it twice with a delay to get the average CPU usage over a period of time.
        cpu_load_percent = psutil.cpu_percent(interval=None)

        # Get memory usage details
        memory_info = psutil.virtual_memory()
        memory_used_percent = memory_info.percent
        memory_used_mbytes = round(
            memory_info.used / 1024 / 1024, 6
        )  # Convert from bytes to MBytes
        memory_total_mbytes = round(
            memory_info.total / 1024 / 1024, 6
        )  # Convert from bytes to MBytes

        self.payload["Metrics"] = {
            "Uptime": uptime,
            "BootTime": boot_time,
            "CPULoadPercent": cpu_load_percent,
            "MemoryUsedPercent": memory_used_percent,
            "MemoryUsedMBytes": memory_used_mbytes,
            "MemoryTotalMBytes": memory_total_mbytes,
            "Disks": [
                # ... disk data ...
            ],
            "Processes": [
                # ... process data ...
            ],
            "docker-services": [
                # ... docker service data ...
            ],
        }

        self.add_disks()
        self.add_processes()
        self.add_docker_services()

    def add_disks(self):
        for partition in psutil.disk_partitions():
            usage = psutil.disk_usage(partition.mountpoint)
            disk_data = {
                "Mountpoint": partition.mountpoint,
                "TotalMbytes": round(
                    usage.total / 1024 / 1024, 6
                ),  # Convert from bytes to MBytes
                "UsedMbytes": round(
                    usage.used / 1024 / 1024, 6
                ),  # Convert from bytes to MBytes
                "UsedPercent": usage.percent,
            }
            self.payload["Metrics"]["Disks"].append(disk_data)

    def add_processes(self):
        for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
            if proc.ppid() == 1:  # Only include parent processes
                # print(json.dumps(proc.info, indent=4))
                MemoryUsedMBytes = ""
                # Convert from bytes to MBytes
                if proc.info["memory_info"] is not None:
                    MemoryUsedMBytes = round(
                        proc.info["memory_info"].rss / 1024 / 1024, 6
                    )

                # cmd line
                cmdLine = ""
                if proc.info["cmdline"] is not None:
                    cmdLine = " ".join(proc.info["cmdline"])
                    cmdLine = (cmdLine[:75] + "...") if len(cmdLine) > 75 else cmdLine

                process_data = {
                    "Name": proc.info["name"],
                    "Command": cmdLine,
                    "MemoryUsedMbytes": MemoryUsedMBytes,
                    "PID": proc.info["pid"],
                    "ParentPID": proc.ppid(),  # Get parent PID
                }
                self.payload["Metrics"]["Processes"].append(process_data)

    def add_docker_services(self):
        client = docker.from_env()
        for container in client.containers.list():
            container_attrs = container.attrs
            # print(container_attrs)
            print("---------------------------------------------------")
            image = container_attrs.get("Image")
            if image is None:
                image = "(None)"
            docker_service_data = {
                "Name": container.name,
                "Image": image,
                # "Command": " ".join(container.attrs["Config"]["Cmd"]),
                # "Environment": {
                #    item.split("=")[0]: item.split("=")[1]
                #    for item in container.attrs["Config"]["Env"]
                #        if "key" or "ETHEREUM_ENDPOINT" is not in item.lower()
                # },
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

            self.payload["Metrics"]["docker-services"].append(docker_service_data)
            print(json.dumps(container_attrs, indent=4))
            # self.payload["Metrics"]["docker-services"].append(container_attrs)

    def get(self):
        usedMB = round(self.payload["Metrics"]["MemoryUsedMBytes"])
        cpu = self.payload["Metrics"]["CPULoadPercent"]
        self.status = f"RAM = {usedMB}mb, CPU = {cpu}%"
        # self.error = ""
        return {
            "Timestamp": self.timestamp,
            "Status": self.status,
            "Error": self.error,
            "Payload": self.payload,
        }
