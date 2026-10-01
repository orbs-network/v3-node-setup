import hashlib
import os
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import yaml
from config import CONTROL_DIR, update_state_file
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


# The commit this process is *running*, captured before any checkout moves the working
# copy. An update is carried out by the code from the previous commit, because control is
# a fresh process each tick started from whatever was checked out at the time - so the
# updater that applies commit N is the one from N-1. Publishing it is what makes "I shipped
# a fix and nothing happened" diagnosable instead of mysterious.
_running_commit = ""

# What this tick saw, recorded by compare() so the status report describes the poll that
# actually ran rather than repeating its git and network calls to find out again. Empty
# when compare() returned before resolving them, which is itself the honest answer.
_branch = ""
_target_commit = ""


def get_running_commit():
    """The commit whose updater code is executing, remembered on first call."""

    global _running_commit

    if not _running_commit:
        _running_commit = get_current_git_commit_hash()

    return _running_commit


def get_update_state():
    """Counters and timestamps that have to outlive a single tick.

    Returns the defaults rather than raising when the file is missing or unreadable, for
    the same reason the applied-commit marker does: a corrupt file must not be able to
    stop the poll.
    """

    default = {
        "last_attempt_at": "",
        "last_success_at": "",
        "last_error": "",
        "consecutive_failures": 0,
    }

    try:
        with open(update_state_file, "r", encoding="utf8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return default

    if not isinstance(stored, dict):
        return default

    return {**default, **stored}


def _write_update_state(state):
    try:
        with open(update_state_file, "w", encoding="utf8") as handle:
            json.dump(state, handle, indent=4)
    except OSError as error:
        logger.error(f"Could not record update state: {error}")


def utc_now():
    """A timestamp a browser will read as UTC.

    `datetime.now().isoformat()` produces no offset and no Z, so anything parsing it takes
    it as local time and renders it wrong by the viewer's offset. The nodes run UTC, which
    is exactly what makes the mistake invisible from here. Matches the format
    system_monitor already publishes for the top-level Timestamp.
    """

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def record_update_attempt():
    state = get_update_state()
    state["last_attempt_at"] = utc_now()
    _write_update_state(state)


def record_update_success():
    state = get_update_state()
    now = utc_now()
    failures = state.get("consecutive_failures", 0)

    state["last_success_at"] = now
    state["last_error"] = ""
    state["consecutive_failures"] = 0
    _write_update_state(state)

    if failures:
        logger.info(f"Update succeeded after {failures} consecutive failures")


def record_update_failure(error):
    """Counts a failed update, so a node failing every minute does not look like one that
    failed once. Nothing else counts this: the commit is not recorded on failure, so the
    next tick retries, and each tick is a new process with no memory of the last."""

    state = get_update_state()
    state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
    state["last_error"] = str(error)
    _write_update_state(state)

    logger.error(f"Update failed ({state['consecutive_failures']} in a row): {error}")


def get_updater_report():
    """The facts a status consumer needs about updating, as structured data.

    Facts only - no verdict on whether any of it is good. The status page owns comparisons.
    """

    state = get_update_state()
    applied = get_applied_commit()
    checked_out = get_current_git_commit_hash()
    failures = int(state.get("consecutive_failures", 0))
    disabled = os.getenv("DONT_UPDATE", "false") == "true"

    if disabled:
        update_state = "disabled"
    elif failures:
        update_state = "failing"
    elif updateTargetTime:
        update_state = "scheduled"
    elif _target_commit and applied and not _target_commit.startswith(applied[:7]) and not applied.startswith(_target_commit[:7]):
        update_state = "behind"
    else:
        update_state = "idle"

    return {
        "Branch": _branch,
        "AppliedCommit": applied,
        "AppliedAt": _applied_at(),
        "CheckedOutCommit": checked_out,
        "RunningCommit": get_running_commit(),
        "TargetCommit": _target_commit,
        "State": update_state,
        "ScheduledFor": updateTargetTime,
        "UpdatesDisabled": disabled,
        "LastAttemptAt": state.get("last_attempt_at", ""),
        "LastSuccessAt": state.get("last_success_at", ""),
        "LastError": state.get("last_error", ""),
        "ConsecutiveFailures": failures,
    }


def _applied_at():
    try:
        with open(applied_commit_file, "r", encoding="utf8") as handle:
            return json.load(handle).get("applied_at", "")
    except (OSError, ValueError, AttributeError):
        return ""


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


def build_images_from_source(docker_compose_file):
    """Rebuilds the services that carry a `build:` section, so their source changes ship.

    `docker compose pull` skips a service that builds from source, and `up -d` reuses
    whatever image is already on disk rather than noticing the source changed. So without
    this a commit touching `logging/` is checked out, logged as `Container logger
    Running`, and recorded as applied while the container keeps running an older build -
    an update that reports success and changed nothing (#71). `logger` is the only such
    service today; everything else runs a pinned image from a registry.

    Reported rather than raised, for two reasons. A failure to build the logger, which is
    observability rather than consensus, must not stop the validator images from
    updating. And raising here would leave `applied_commit.json` behind, so the next poll
    would see "checked out but never applied" and retry the whole update - `docker
    compose pull` included - every minute.
    """

    logger.info("Building images for services that build from source")

    try:
        run(["docker", "compose", "-f", docker_compose_file, "build"])
    except CommandError as error:
        set_error(f"Failed to build images from source - keeping the existing ones: {error.output}")


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
            json.dump({"commit": commit_hash, "applied_at": utc_now()}, file, indent=4)
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
    global isInUpdatingState, updateTargetTime, _branch, _target_commit

    logger.debug("Comparing current state with metadata")

    # Before anything can move the working copy, so this records the code that is running
    # rather than the code that is about to be checked out.
    get_running_commit()
    _branch = extract_branch_name()

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

    _target_commit = scheduled_commit_hash

    if updateMode == "scheduled":
        logger.debug("Scheduled update mode")
        updateResolution = metadata.get("updateResolution", 1440)
        logger.debug(f"Update resolution: {updateResolution} minutes")
        timeToUpdate = get_my_update_schedule_window_time(updateResolution, scheduled_commit_hash)
        updateTargetTime = int(timeToUpdate.timestamp())

        set_status_for_ui(f"Update scheduled for {timeToUpdate}")

        logger.debug(f"Time to update: {timeToUpdate}")
        if datetime.now() < timeToUpdate:
            logger.debug("Not my time to update")
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
        # Debug, not info: this fires on every one of the 1440 polls a day, and the same
        # fact is now in Payload.Updater as AppliedCommit with State "idle". Repeating it
        # every minute would bury the updater's actual actions in its own log.
        logger.debug(f"I'm up to date with commit hash: {current_commit_hash} / {current_git_tag}, scheduled commit hash: {scheduled_commit_hash}")
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
    """Applies an update and records whether it worked.

    The counting lives in this wrapper so that a failure is recorded before the exception
    propagates, and so the outcome is recorded once however the update was reached. A node
    whose update fails never records the commit, so the next tick retries - every minute,
    forever, in a fresh process each time. Without a counter on disk, a node that has
    failed two thousand times running is indistinguishable from one that failed once.
    """

    logger.info(f"Triggering update for commit hash: {scheduled_commit_hash}")

    # Checked before the attempt is counted: refusing to update is not an attempt at one.
    if os.getenv("DONT_UPDATE", "false") == "true":
        set_status_for_ui("DONT_UPDATE is set to true - skipping update")
        logger.info("DONT_UPDATE is set to true, skipping update")
        return

    record_update_attempt()
    started = datetime.now()

    try:
        _apply_update(scheduled_commit_hash)
    except Exception as error:
        record_update_failure(error)
        raise

    record_update_success()
    logger.info(f"Update to {scheduled_commit_hash} took {(datetime.now() - started).total_seconds():.1f}s")


def _apply_update(scheduled_commit_hash):
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

    # Before the pull, so both sources of images are settled before anything is started.
    build_images_from_source(docker_compose_file)

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
