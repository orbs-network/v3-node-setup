import hashlib
import os
import re
import subprocess
from datetime import datetime, timedelta

import requests
import yaml
from logger import logger

globalError = ""
statusForUi = []
isInUpdatingState = False
updateTargetTime = 0

# ---- UPDATE-DESCRIPTOR-BEGIN ----
# targetNodes:
#   - id: 8c824c84e03de12e73fe286222c00faa3d8fd152
#   - id: 1c824c84e03de12e73fe286222c00faa3d8fd152
#   - id: *
# updateResolution: 1440
# updateMode: immediate , scheduled
# updateInAction: false
# commit: 64816f4876aa1483ba79ee5e9b061985ccd2b6b1
# ---- UPDATE-DESCRIPTOR-END ----


def get_updating_state_for_ui():
    global isInUpdatingState, updateTargetTime

    if isInUpdatingState:
        return '{"status": "updating", "time": ' + str(updateTargetTime) + "}"
    else:
        return ""
    # return "updating" if isInUpdatingState else ""


def get_status_for_ui():
    global statusForUi
    if len(statusForUi) == 0:
        return "OK"
    return ", ".join(statusForUi)


def set_status_for_ui(status):
    global statusForUi
    status = status.replace(",", " ")
    if status != "OK" and status != "Error":
        status = "• " + status

    if len(statusForUi) > 0 and statusForUi[len(statusForUi) - 1] == status:
        return

    statusForUi.insert(0, status)
    if len(statusForUi) > 5:
        statusForUi = statusForUi[:5]


def set_error(error):
    global globalError
    if globalError == error:
        return

    logger.error(f"Setting status error: {error}")
    globalError = error
    set_status_for_ui("Error")


def get_error():
    global globalError
    return globalError


def fetch_remote_descriptor():
    # url = os.getenv('DOCKER_COMPOSE_DESCRIPTOR_URL', "https://raw.githubusercontent.com/orbs-network/v3-node-setup/refs/heads/main/deployment/docker-compose.yml")
    url = os.getenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/main:deployment/docker-compose.yml")

    try:
        logger.info(f"Fetching remote descriptor from remote git {url}")
        data = os.popen(f"git fetch origin").read()
        logger.info(f"Fetch result: {data}")
        data = os.popen(f"git show {url}").read()
        # response = requests.get(url)
        # response.raise_for_status()  # Check for HTTP errors
        # data = response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"An error occurred while fetching the file: {e}")
        data = None

    return data


def fetch_and_parse_metadata():
    # try:
    logger.info("Fetching and parsing metadata...")
    content = fetch_remote_descriptor()

    # Extract the metadata section
    descriptor_begin = "# ---- UPDATE-DESCRIPTOR-BEGIN ----"
    descriptor_end = "# ---- UPDATE-DESCRIPTOR-END ----"

    # Find the metadata section between begin and end markers
    metadata_match = re.search(rf"{re.escape(descriptor_begin)}(.*?){re.escape(descriptor_end)}", content, re.DOTALL)

    if not metadata_match:
        raise ValueError("Descriptor section not found in file")

    # Extract metadata content and strip the comments
    metadata_content = metadata_match.group(1)
    metadata_content = re.sub(r"^\s*#\s*", "", metadata_content, flags=re.MULTILINE).strip()

    # Parse as YAML and return
    metadata_dict = yaml.safe_load(metadata_content)
    return metadata_dict

    # except requests.exceptions.RequestException as e:
    #     print(f"An error occurred while fetching the file: {e}")
    #     return None
    # except ValueError as e:
    #     print(f"Error: {e}")
    #     return None
    # except Exception as e:
    #     print(f"An error occurred: {e}")
    #     return None


# def get_current_git_tag ():
#     try:
#         logger.info("Fetching current git tag...")
#         tag = os.popen("git describe --tags $(git rev-list --tags --max-count=1)").read().strip()
#         return tag
#     except Exception as e:
#         logger.error(f"An error occurred while fetching the current git tag: {e}")
#         return None


def get_current_git_tag():
    try:
        logger.info("Fetching current git tag...")
        tag = os.popen("git describe --tags --exact-match").read().strip()
        return tag
    except Exception as e:
        logger.error(f"An error occurred while fetching the current git tag: {e}")
        return None


def get_current_git_commit_hash():
    try:
        commit_hash = os.popen("git rev-parse HEAD").read().strip()
        logger.info(f"Fetching current git commit hash {commit_hash}")
        return commit_hash
    except Exception as e:
        logger.error(f"An error occurred while fetching the current git commit hash: {e}")
        return None


def get_guardian_node_id():
    return os.getenv("NODE_ADDRESS", None)


def get_timestamp_of_commit_hash(commit_hash):
    try:
        unixtime = os.popen(f"git show -s --format=%ct {commit_hash}").read().strip()
        timestamp = datetime.fromtimestamp(int(unixtime))
        logger.info(f"Baseline commit hash timestamp: {timestamp} for commit: {commit_hash}")

        return timestamp

    except Exception as e:
        logger.error(f"An error occurred while fetching the timestamp of commit hash: {e}")
        return None


def get_my_update_schedule_window_time(spread_minutes, commit_hash):
    hash_value = get_guardian_node_id()
    hash_int = int(hashlib.sha256(hash_value.encode()).hexdigest(), 16)
    minute_of_day = hash_int % spread_minutes
    # today = datetime.now().replace(second=0, microsecond=0)
    baseline_time = get_timestamp_of_commit_hash(commit_hash)
    # today = datetime.strptime(baseline_time, "%Y-%m-%d %H:%M:%S %z").replace(second=0, microsecond=0)
    target_time = baseline_time + timedelta(minutes=minute_of_day)

    return target_time


def extract_branch_name():
    git_url = os.getenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/main:deployment/docker-compose.yml")

    if ":" in git_url:
        branch = git_url.split(":")[0]  # Get the part before the colon
        if "/" in branch:
            return branch.split("/")[-1]  # Get the part after the last '/'
        return branch
    return None  # Return None if format is invalid


def get_remote_latest_commit_hash():
    # Step 1: Get the current branch name
    branch_name = extract_branch_name()

    # Step 2: Get the latest commit ID from the remote for the current branch
    commit_id = subprocess.check_output(["git", "ls-remote", "origin", branch_name], text=True).split()[0]

    logger.info(f"Latest commit hash for branch {branch_name}: {commit_id}")

    return commit_id


def compare():
    global isInUpdatingState, updateTargetTime

    logger.info("Comparing current state with metadata")

    metadata = fetch_and_parse_metadata()
    guardian_node_id = get_guardian_node_id()

    if guardian_node_id is None:
        logger.error("Guardian node ID not found")
        return

    # Check if I'm in the target list in any way.
    target_nodes = metadata.get("targetNodes", [])
    am_i_a_target = False
    for node in target_nodes:
        if node.get("id") == guardian_node_id or node.get("id") == "*":
            am_i_a_target = True
            break

    logger.info(f"Am I a target node? {am_i_a_target}")

    if not am_i_a_target:
        return

    # Check if the update is in action
    update_in_action = metadata.get("updateInAction", False)

    if not update_in_action:
        logger.info("Update is NOT in action, skipping")
        return

    # Check if I need to update myself.

    isInUpdatingState = True

    updateMode = metadata.get("updateMode", "immediate")

    current_git_tag = get_current_git_tag()
    current_commit_hash = get_current_git_commit_hash()
    scheduled_commit_hash = metadata.get("commit")
    if scheduled_commit_hash == "latest":
        scheduled_commit_hash = get_remote_latest_commit_hash()

    if updateMode == "scheduled":
        logger.info("Scheduled update mode")
        updateResolution = metadata.get("updateResolution", 1440)
        logger.info(f"Update resolution: {updateResolution} minutes")
        timeToUpdate = get_my_update_schedule_window_time(updateResolution, scheduled_commit_hash)
        updateTargetTime = int(timeToUpdate.timestamp())

        set_status_for_ui(f"Update scheduled for {timeToUpdate}")

        logger.info(f"Time to update: {timeToUpdate}")
        if datetime.now() < timeToUpdate:
            logger.info("Not my time to update")
            return

    updateTargetTime = 0

    if current_commit_hash.startswith(scheduled_commit_hash) or current_git_tag == scheduled_commit_hash:
        logger.info(f"I'm up to date with commit hash: {current_commit_hash} / {current_git_tag}, scheduled commit hash: {scheduled_commit_hash}")
        set_status_for_ui(f"I'm up to date with commit hash: {current_commit_hash} / {current_git_tag}")
    else:
        logger.info(f"I need to update, current commit hash: {current_commit_hash}, scheduled commit hash: {scheduled_commit_hash}")
        set_status_for_ui(f"Update in progress for commit hash: {scheduled_commit_hash}")
        trigger_update(scheduled_commit_hash)

    isInUpdatingState = False


def trigger_update(scheduled_commit_hash):
    logger.info(f"Triggering update for commit hash: {scheduled_commit_hash}")

    if os.getenv("DONT_UPDATE", "false") == "true":
        set_status_for_ui("DONT_UPDATE is set to true - skipping update")
        logger.info("DONT_UPDATE is set to true, skipping update")
        return

    # fetch latest changes.

    logger.info("Fetching latest changes")
    res = os.popen("git fetch origin").read()
    logger.info(res)

    # stash any local changes
    logger.info("Stashing any local changes")
    res = os.popen("git stash").read()
    logger.info(res)

    logger.info(f"Checking out commit {scheduled_commit_hash}")
    res = os.popen(f"git checkout {scheduled_commit_hash}").read()
    logger.info(res)

    docker_compose_file = os.getenv("DOCKER_COMPOSE_FILE")
    logger.info(f"Running docker-compose -f {docker_compose_file} up -d")
    res = os.popen(f"docker-compose -f {docker_compose_file} up -d").read()
    logger.info(res)

    logger.info("Update completed")
