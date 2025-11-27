import os

import yaml
import subprocess
import sys


def load_docker_compose(file_path):
    """Load the docker-compose.yml file."""
    try:
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Error reading docker-compose.yml: {e}")
        sys.exit(1)


def extract_healthchecks(compose_data):
    """Extract healthcheck test commands from the docker-compose data."""
    healthchecks = {}
    services = compose_data.get("services", {})

    for service_name, service_config in services.items():
        healthcheck = service_config.get("healthcheck", {})
        test_command = healthcheck.get("test")

        if isinstance(test_command, str):  # Ensure it's a string
            healthchecks[service_name] = test_command

    return healthchecks


def execute_command_in_container(container_name, command):
    """Execute the given command inside a running container."""
    try:
        result = subprocess.run(
            ["podman", "exec", container_name] + command.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", f"Error executing command: {e}"


def main():
    compose_file = os.getenv('DOCKER_COMPOSE_FILE')
    compose_data = load_docker_compose(compose_file)
    healthchecks = extract_healthchecks(compose_data)

    if not healthchecks:
        print("No healthchecks found in docker-compose.yml.")
        return

    print("Found healthchecks:")
    for service, command in healthchecks.items():
        print(f"Service: {service}, Command: {command}")

    print("\nExecuting healthcheck commands:")
    for service, command in healthchecks.items():
        print(f"\n--- Service: {service} ---")
        # Assume the container name matches the service name (may need adjustment)
        container_name = service
        exit_code, stdout, stderr = execute_command_in_container(container_name, command)

        print(f"Command: {command}")
        print(f"Exit Code: {exit_code}")
        print("Output:")
        print(stdout or "No output")
        if stderr:
            print("Error Output:")
            print(stderr)


if __name__ == "__main__":
    main()
