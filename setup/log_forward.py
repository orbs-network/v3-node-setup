"""
Watches for ctr.log files in the podman containers directory and copies them to a shared directory
that is then exposed via nginx.
"""

import os
import shutil
import stat
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# TODO: use $HOME instead of /home/ubuntu
CONTAINERS_PATH = os.path.expanduser("/home/ubuntu/.local/share/containers/storage/overlay-containers/")
DESTINATION_BASE = "/opt/orbs"

class LogHandler(FileSystemEventHandler):
    def on_modified(self, event: 'FileSystemEvent') -> None:
        if not event.is_directory and event.src_path.endswith("/userdata/ctr.log"):
            container_id = os.path.basename(os.path.dirname(os.path.dirname(event.src_path)))
            container_name = get_container_name(container_id)
            if container_name:
                destination = os.path.join(DESTINATION_BASE, container_name)
                os.makedirs(destination, exist_ok=True)
                shutil.copy2(event.src_path, os.path.join(destination, "ctr.log"))
                # Update file perms (-rw-r--r--)
                os.chmod(os.path.join(destination, "ctr.log"), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

def get_container_name(container_id: str) -> str:
    result = subprocess.run(
        ["podman", "ps", "-a", "--format", "{{.ID}} {{.Names}}"],
        capture_output=True,
        text=True,
    )
    lines = result.stdout.split("\n")
    for line in lines:
        if line.startswith(container_id[:12]):
            container_name = line.split()[1]
            return container_name

if __name__ == "__main__":
    event_handler = LogHandler()
    observer = Observer()
    observer.schedule(event_handler, CONTAINERS_PATH, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
