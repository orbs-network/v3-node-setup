import hashlib
import os
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta

import yaml
from config import CONTROL_DIR
from identity import bare_address, get_node_address
from logger import logger
from utils import CommandError, run

# Fixed by container_name in docker-compose.yml, so it does not move with the project name.
NGINX_CONTAINER = "nginx"

# The commit whose update ran all the way through, which is not the same thing as the
# commit that is checked out: the checkout happens first, so a compose failure leaves the
# working copy at the target while nothing was actually applied.
applied_commit_file = os.path.join(CONTROL_DIR, "applied_commit.json")

globalError = ""
statusForUi = []
isInUpdatingState = False
updateTargetTime = 0

# The descriptor that actually drives updates lives at the top of docker-compose.yml on
# the remote branch. It is read from there, never from this file.


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


def get_remote_git_path():
    """Returns the configured remote path to the descriptor, eg. `origin/main:docker-compose.yml`

    There is deliberately no default. The previous one pointed at a file on `origin/main`
    that carries no descriptor at all, so an unset variable failed later with a message
    about a missing descriptor section rather than about the missing setting.
    """

    path = os.getenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "").strip()

    if not path:
        raise ValueError("DOCKER_COMPOSE_REMOTE_GIT_PATH is not set, so there is no descriptor to read")

    return path


def fetch_remote_descriptor():
    """Returns the contents of the descriptor file on the configured remote branch"""

    path = get_remote_git_path()

    logger.debug(f"Fetching remote descriptor from remote git {path}")

    # Both raise with git's own message if they fail, rather than returning empty content
    # that only fails later as a confusing "descriptor section not found".
    run(["git", "fetch", "origin"])

    return run(["git", "show", path])


def fetch_and_parse_metadata():
    # try:
    logger.debug("Fetching and parsing metadata...")
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


def get_current_git_tag():
    """Returns the tag at HEAD, or an empty string when there is none.

    The updater checks out commit hashes, so an untagged detached HEAD is the normal
    state rather than a failure. git reports that on stderr, which os.popen let through
    to the log on every single poll, so it is captured and discarded here.
    """

    result = subprocess.run(["git", "describe", "--tags", "--exact-match"], capture_output=True, text=True, check=False)

    return result.stdout.strip()


def get_current_git_commit_hash():
    """Returns the commit currently checked out"""

    commit_hash = run(["git", "rev-parse", "HEAD"])
    logger.debug(f"Fetching current git commit hash {commit_hash}")

    return commit_hash


def get_free_disk_gb():
    """Returns the free space on the filesystem holding the Docker images"""

    for path in (os.getenv("DOCKER_DATA_ROOT", "/var/lib/docker"), "/"):
        try:
            return shutil.disk_usage(path).free / (1024**3)
        except OSError:
            continue

    return 0.0


def container_is_running(name):
    """Whether a container exists and is currently running."""

    try:
        return run(["docker", "inspect", "-f", "{{.State.Running}}", name]) == "true"
    except CommandError:
        return False


def reload_nginx():
    """Makes nginx apply configuration changes that arrived with this update.

    `nginx/conf.d` is a bind mount, so the checkout updates the file inside the container
    immediately - but compose decides whether to recreate a container from a hash of its
    service definition, not of its mounted file contents, so `up -d` leaves nginx alone.
    nginx reads its configuration only at startup or on SIGHUP. Without this, an nginx
    config change reaches every node and silently never takes effect, which is how the
    log endpoints stayed broken across a fleet that reported itself up to date (#81).

    Unconditional, rather than only when the update touched `nginx/`. Gating on a diff
    would mean trusting `applied_commit.json`, which is absent on the bootstrap path and
    misleading after a half-failed update - buying a silent failure mode, whose symptom
    is indistinguishable from the bug this fixes, to skip an operation that is free. A
    reload forks new workers on the new configuration and lets the old ones drain their
    in-flight requests, and it only runs on git promotion, never on a poll.

    It also re-resolves upstreams. A literal hostname in `proxy_pass` is resolved once at
    load and cached for the life of the process, so reloading bounds the damage from one
    to a single update cycle rather than forever (#70).

    Deliberately never raises. The containers are already updated by the time this runs,
    so failing here would leave `applied_commit.json` behind, and the next poll would see
    "checked out but never applied" and retry the whole update - `docker compose pull`
    included - every single minute.
    """

    if not container_is_running(NGINX_CONTAINER):
        set_error(f"{NGINX_CONTAINER} is not running - its configuration was not reloaded")
        return

    try:
        # Validates the configuration as actually mounted in the container. If it is
        # broken the running workers keep serving the last good one, which is the safe
        # outcome - but a broken config must not look like a clean update.
        run(["docker", "exec", NGINX_CONTAINER, "nginx", "-t"])
    except CommandError as error:
        set_error(f"{NGINX_CONTAINER} configuration is invalid - not reloading: {error.output}")
        return

    try:
        run(["docker", "exec", NGINX_CONTAINER, "nginx", "-s", "reload"])
    except CommandError as error:
        set_error(f"Failed to reload {NGINX_CONTAINER}: {error.output}")
        return

    logger.info(f"Reloaded {NGINX_CONTAINER} configuration")


def prune_images():
    """Removes images left dangling by a pull, so updates do not accumulate them"""

    logger.info("Pruning dangling images")

    # Only dangling images, never `-a`: an image can be untagged and still be the one a
    # stopped container needs. A pull that moves a tag leaves the old image dangling,
    # which is exactly the case this reclaims.
    run(["docker", "image", "prune", "-f"], check=False)


def ensure_disk_headroom():
    """Raises when there is too little free space to pull images safely"""

    required_gb = float(os.getenv("MIN_FREE_DISK_GB", "5"))
    free_gb = get_free_disk_gb()

    if free_gb >= required_gb:
        logger.info(f"{free_gb:.1f}GB free, enough to pull")
        return

    # A pull downloads the new images while the old ones are still on disk, so running it
    # without headroom can fill the filesystem and take the node down.
    logger.info(f"Only {free_gb:.1f}GB free, below the {required_gb}GB needed - pruning first")
    prune_images()

    free_gb = get_free_disk_gb()

    if free_gb < required_gb:
        raise RuntimeError(f"Not enough free disk to pull images: {free_gb:.1f}GB free, {required_gb}GB required")

    logger.info(f"{free_gb:.1f}GB free after pruning, enough to pull")


def report_local_modifications():
    """Records any local edits to tracked files, which the checkout is about to discard"""

    # Untracked files are excluded: the checkout leaves those alone, so they are not
    # about to be lost and do not belong in this warning.
    changes = run(["git", "status", "--porcelain", "--untracked-files=no"])

    if not changes:
        return

    files = " ".join(line[3:] for line in changes.splitlines() if len(line) > 3)

    # A node is a deployment target rather than somewhere to edit, so a modified tracked
    # file is itself the anomaly worth surfacing - not just the fact it is being dropped.
    logger.error(f"Discarding local modifications to tracked files: {files}")
    set_status_for_ui(f"Discarded local modifications: {files}")


def get_applied_commit():
    """Returns the commit whose update last completed, or an empty string if none has"""

    try:
        with open(applied_commit_file, encoding="utf8") as file:
            return json.load(file).get("commit", "")
    except (OSError, ValueError, AttributeError):
        return ""


def set_applied_commit(commit_hash):
    """Records that the update for this commit ran all the way through"""

    logger.info(f"Recording {commit_hash} as applied")

    try:
        with open(applied_commit_file, "w", encoding="utf8") as file:
            json.dump({"commit": commit_hash, "applied_at": datetime.now().isoformat()}, file, indent=4)
    except OSError as error:
        # Losing the marker means the next poll retries an update that already succeeded,
        # which is wasteful but safe. Failing the poll over it would not be.
        logger.error(f"Could not record the applied commit: {error}")


def get_timestamp_of_commit_hash(commit_hash):
    """Returns when the commit was made, used to anchor a scheduled update window"""

    unixtime = run(["git", "show", "-s", "--format=%ct", commit_hash])
    timestamp = datetime.fromtimestamp(int(unixtime))
    logger.debug(f"Baseline commit hash timestamp: {timestamp} for commit: {commit_hash}")

    return timestamp


def get_my_update_schedule_window_time(spread_minutes, commit_hash):
    # Hashed in its normalised form so the window a node lands in does not move just
    # because the address was written with a prefix or in different casing.
    hash_value = bare_address(get_node_address())
    hash_int = int(hashlib.sha256(hash_value.encode()).hexdigest(), 16)
    minute_of_day = hash_int % spread_minutes
    # today = datetime.now().replace(second=0, microsecond=0)
    baseline_time = get_timestamp_of_commit_hash(commit_hash)
    # today = datetime.strptime(baseline_time, "%Y-%m-%d %H:%M:%S %z").replace(second=0, microsecond=0)
    target_time = baseline_time + timedelta(minutes=minute_of_day)

    return target_time


def extract_branch_name():
    git_url = os.getenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/main:deployment/docker-compose.yml")

    ref = git_url.split(":")[0]

    if "/" not in ref:
        return ref

    # Strip only the remote name. Keeping just the last segment turned feature/v5-ready
    # into v5-ready, which git happened to still match by trailing path component - right
    # up until two branches share a final segment, when ls-remote returns both.
    _, _, branch = ref.partition("/")

    return branch


def get_remote_latest_commit_hash():
    """Returns the commit at the tip of the configured remote branch"""

    branch_name = extract_branch_name()

    if not branch_name:
        raise ValueError(f"Could not read a branch name from DOCKER_COMPOSE_REMOTE_GIT_PATH: {get_remote_git_path()}")

    matches = [line for line in run(["git", "ls-remote", "origin", branch_name]).splitlines() if line.strip()]

    # ls-remote exits zero and prints nothing when the branch does not resolve, and prints
    # several lines when the name is ambiguous. Taking the first field of either would be
    # an IndexError or, worse, silently the wrong commit.
    if not matches:
        raise ValueError(f"Branch {branch_name} does not resolve to a commit on origin")

    if len(matches) > 1:
        raise ValueError(f"Branch {branch_name} matches {len(matches)} refs on origin, refusing to guess between them")

    commit_id = matches[0].split()[0]

    logger.debug(f"Latest commit hash for branch {branch_name}: {commit_id}")

    return commit_id


def compare():
    global isInUpdatingState, updateTargetTime

    logger.debug("Comparing current state with metadata")

    metadata = fetch_and_parse_metadata()
    node_address = get_node_address()

    if not node_address:
        logger.error("NODE_ADDRESS is not set, cannot tell whether this node is a target")
        return

    # Check if I'm in the target list in any way. Both sides are normalised, so a
    # descriptor written with a 0x prefix or different casing still matches.
    target_nodes = metadata.get("targetNodes", [])
    wanted = bare_address(node_address)
    am_i_a_target = False
    for node in target_nodes:
        node_id = str(node.get("id", ""))
        if node_id == "*" or bare_address(node_id) == wanted:
            am_i_a_target = True
            break

    logger.debug(f"Am I a target node? {am_i_a_target}")

    if not am_i_a_target:
        return

    # Check if the update is in action
    update_in_action = metadata.get("updateInAction", False)

    if not update_in_action:
        logger.debug("Update is NOT in action, skipping")
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

    is_checked_out = current_commit_hash.startswith(scheduled_commit_hash) or current_git_tag == scheduled_commit_hash
    applied_commit = get_applied_commit()

    if not applied_commit:
        # First poll since this check existed. Adopt whatever is checked out rather than
        # forcing an update, so introducing the marker does not restart every node's
        # services to tell us something we can already see.
        applied_commit = current_commit_hash
        set_applied_commit(current_commit_hash)
        logger.info(f"No applied commit on record, adopting the checked out {current_commit_hash}")

    if is_checked_out and applied_commit == current_commit_hash:
        logger.info(f"I'm up to date with commit hash: {current_commit_hash} / {current_git_tag}, scheduled commit hash: {scheduled_commit_hash}")
        set_status_for_ui(f"I'm up to date with commit hash: {current_commit_hash} / {current_git_tag}")
    else:
        if is_checked_out:
            # The checkout landed but the update did not finish, so the working copy looks
            # current while nothing was applied. Without this the node would report itself
            # up to date forever.
            logger.info(f"Commit {current_commit_hash} is checked out but was never applied, retrying")
            set_status_for_ui(f"Retrying an update that did not complete for {current_commit_hash}")
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

    # Read this before touching the checkout, so a missing setting fails the update before
    # it has moved the working copy halfway to the new commit.
    docker_compose_file = os.getenv("DOCKER_COMPOSE_FILE")
    if not docker_compose_file:
        raise ValueError("DOCKER_COMPOSE_FILE is not set, cannot apply the update")

    # fetch latest changes.

    logger.info("Fetching latest changes")
    run(["git", "fetch", "origin"])

    report_local_modifications()

    branch = extract_branch_name()

    logger.info(f"Checking out commit {scheduled_commit_hash}")

    if branch:
        # -B leaves the working copy on the configured branch instead of detached, so the
        # state is legible to anyone who logs in. -f discards local edits to tracked files
        # rather than stashing them, which used to leave a stash behind on every update
        # and never dropped one.
        run(["git", "checkout", "-f", "-B", branch, scheduled_commit_hash])
    else:
        run(["git", "checkout", "-f", scheduled_commit_hash])

    ensure_disk_headroom()

    # `up -d` alone only recreates a container when the image reference changes, so an
    # image re-pushed under the same tag would never be picked up without this.
    logger.info(f"Running docker compose -f {docker_compose_file} pull")
    run(["docker", "compose", "-f", docker_compose_file, "pull"])

    # --remove-orphans stops containers dropped from the compose file. Without it they
    # keep running unmanaged, and an abandoned container's writable layer grows without
    # anything ever reclaiming it.
    logger.info(f"Running docker compose -f {docker_compose_file} up -d --remove-orphans")
    run(["docker", "compose", "-f", docker_compose_file, "up", "-d", "--remove-orphans"])

    # After the containers are up, so a reload never races a container still starting.
    reload_nginx()

    # After the containers are running, so nothing still in use is removed.
    prune_images()

    # Only reached when every step above succeeded, since they raise otherwise. Recording
    # the checked out commit rather than the requested one, so a tag resolves to a hash.
    set_applied_commit(get_current_git_commit_hash())

    logger.info("Update completed")
