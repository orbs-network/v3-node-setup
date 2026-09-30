"""updater applied-commit tests"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import updater
from utils import CommandError


@pytest.fixture(autouse=True)
def isolated_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives each test its own applied-commit marker, and a compose file to point at"""

    monkeypatch.setattr(updater, "applied_commit_file", str(tmp_path / "applied_commit.json"))
    monkeypatch.setenv("DOCKER_COMPOSE_FILE", str(tmp_path / "docker-compose.yml"))
    monkeypatch.setenv("DONT_UPDATE", "false")


def test_no_applied_commit_is_recorded_initially() -> None:
    """Test that a node with no marker reports nothing rather than guessing"""

    assert updater.get_applied_commit() == ""


def test_applied_commit_round_trips() -> None:
    """Test that a recorded commit is read back"""

    updater.set_applied_commit("abc123")

    assert updater.get_applied_commit() == "abc123"


def test_an_unreadable_marker_reports_nothing(tmp_path: Path) -> None:
    """Test that a corrupt marker is treated as absent rather than raising"""

    Path(updater.applied_commit_file).write_text("not json at all", encoding="utf8")

    assert updater.get_applied_commit() == ""


def test_a_completed_update_records_the_commit(mocker: MockerFixture) -> None:
    """Test that finishing an update records the commit that is checked out"""

    mocker.patch.object(updater, "run")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")

    updater.trigger_update("deadbeef")

    assert updater.get_applied_commit() == "deadbeef"


def test_a_failed_compose_does_not_record_the_commit(mocker: MockerFixture) -> None:
    """Test that a failed update leaves no applied marker, so the next poll retries it"""

    # This is the bug the marker exists for: the checkout happens before compose, so
    # without it a failed compose leaves the node looking current forever.
    def fail_on_compose(command: list, check: bool = True) -> str:
        if "compose" in command:
            raise CommandError(command, 1, "compose blew up")
        return ""

    mocker.patch.object(updater, "run", side_effect=fail_on_compose)
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")

    with pytest.raises(CommandError):
        updater.trigger_update("deadbeef")

    assert updater.get_applied_commit() == ""


def test_a_skipped_update_does_not_record_the_commit(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that DONT_UPDATE leaves no marker, since nothing was applied"""

    monkeypatch.setenv("DONT_UPDATE", "true")
    mocker.patch.object(updater, "run")

    updater.trigger_update("deadbeef")

    assert updater.get_applied_commit() == ""


def _stub_compare(mocker: MockerFixture, current: str, scheduled: str) -> object:
    """Points compare() at a fixed remote state and stubs out the update itself"""

    mocker.patch.object(updater, "fetch_and_parse_metadata", return_value={
        "targetNodes": [{"id": "*"}],
        "updateInAction": True,
        "updateMode": "immediate",
        "commit": "latest",
    })
    mocker.patch.object(updater, "get_node_address", return_value="0xnode1")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value=current)
    mocker.patch.object(updater, "get_current_git_tag", return_value="")
    mocker.patch.object(updater, "get_remote_latest_commit_hash", return_value=scheduled)

    return mocker.patch.object(updater, "trigger_update")


def test_an_applied_commit_is_left_alone(mocker: MockerFixture) -> None:
    """Test that a node which finished its update is not updated again"""

    trigger = _stub_compare(mocker, current="abc123", scheduled="abc123")
    updater.set_applied_commit("abc123")

    updater.compare()

    trigger.assert_not_called()


def test_a_first_poll_adopts_the_checked_out_commit(mocker: MockerFixture) -> None:
    """Test that introducing the marker does not force an update on a healthy node"""

    trigger = _stub_compare(mocker, current="abc123", scheduled="abc123")

    updater.compare()

    trigger.assert_not_called()
    assert updater.get_applied_commit() == "abc123"


def test_a_checked_out_but_unapplied_commit_is_retried(mocker: MockerFixture) -> None:
    """Test that a half-finished update is retried rather than reported as up to date"""

    trigger = _stub_compare(mocker, current="abc123", scheduled="abc123")
    updater.set_applied_commit("older99")

    updater.compare()

    trigger.assert_called_once_with("abc123")


def test_an_update_pulls_before_bringing_containers_up(mocker: MockerFixture) -> None:
    """Test that images are pulled, then recreated, then pruned, in that order"""

    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    run = mocker.patch.object(updater, "run")

    updater.trigger_update("deadbeef")

    docker_steps = [call.args[0] for call in run.call_args_list if call.args[0][0] == "docker"]

    # By position in the sequence rather than adjacency: the nginx reload also issues
    # docker commands between bringing the containers up and pruning.
    pull = next(i for i, step in enumerate(docker_steps) if step[-1] == "pull")
    up = next(i for i, step in enumerate(docker_steps) if "--remove-orphans" in step)
    prune = docker_steps.index(["docker", "image", "prune", "-f"])

    assert pull < up < prune


def test_pruning_happens_after_the_containers_are_running(mocker: MockerFixture) -> None:
    """Test that a failed up -d stops the update before anything is pruned"""

    # Pruning ahead of a successful `up` could remove an image a container still needs.
    def fail_on_up(command: list, check: bool = True) -> str:
        if "up" in command:
            raise CommandError(command, 1, "up blew up")
        return ""

    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    run = mocker.patch.object(updater, "run", side_effect=fail_on_up)

    with pytest.raises(CommandError):
        updater.trigger_update("deadbeef")

    assert ["docker", "image", "prune", "-f"] not in [call.args[0] for call in run.call_args_list]
    assert updater.get_applied_commit() == ""


def test_enough_disk_skips_the_prune(mocker: MockerFixture) -> None:
    """Test that healthy free space does not trigger a prune"""

    mocker.patch.object(updater, "get_free_disk_gb", return_value=20.0)
    prune = mocker.patch.object(updater, "prune_images")

    updater.ensure_disk_headroom()

    prune.assert_not_called()


def test_low_disk_prunes_and_continues_when_that_frees_enough(mocker: MockerFixture) -> None:
    """Test that a prune which recovers enough space lets the update proceed"""

    mocker.patch.object(updater, "get_free_disk_gb", side_effect=[1.0, 20.0])
    prune = mocker.patch.object(updater, "prune_images")

    updater.ensure_disk_headroom()

    prune.assert_called_once()


def test_low_disk_aborts_when_pruning_does_not_free_enough(mocker: MockerFixture) -> None:
    """Test that the update is refused rather than filling the filesystem"""

    mocker.patch.object(updater, "get_free_disk_gb", side_effect=[1.0, 1.2])
    mocker.patch.object(updater, "prune_images")

    with pytest.raises(RuntimeError, match="Not enough free disk"):
        updater.ensure_disk_headroom()


def test_branch_name_keeps_every_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a branch containing slashes is not truncated to its last segment"""

    # Truncating gave "v5-ready", which git matched by trailing path component until two
    # branches shared a final segment - then ls-remote returns both and picking the first
    # silently deploys the wrong commit.
    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/feature/v5-ready:docker-compose.yml")

    assert updater.extract_branch_name() == "feature/v5-ready"


def test_branch_name_handles_a_single_segment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a plain remote/branch pair still resolves"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/main:docker-compose.yml")

    assert updater.extract_branch_name() == "main"


def test_an_unset_remote_path_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a missing setting is reported as itself, not as a missing descriptor"""

    monkeypatch.delenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", raising=False)

    with pytest.raises(ValueError, match="DOCKER_COMPOSE_REMOTE_GIT_PATH is not set"):
        updater.get_remote_git_path()


def test_an_unresolvable_branch_is_reported(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ls-remote returning nothing raises a message naming the branch"""

    # ls-remote exits zero and prints nothing, so .split()[0] used to raise IndexError.
    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/nope:docker-compose.yml")
    mocker.patch.object(updater, "run", return_value="")

    with pytest.raises(ValueError, match="does not resolve"):
        updater.get_remote_latest_commit_hash()


def test_an_ambiguous_branch_refuses_to_guess(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a name matching several refs raises rather than picking one"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/v5-ready:docker-compose.yml")
    mocker.patch.object(updater, "run", return_value="aaa111\trefs/heads/feature/v5-ready\nbbb222\trefs/heads/hotfix/v5-ready")

    with pytest.raises(ValueError, match="refusing to guess"):
        updater.get_remote_latest_commit_hash()


def test_a_resolvable_branch_returns_its_commit(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the normal case returns the commit at the branch tip"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/feature/v5-ready:docker-compose.yml")
    mocker.patch.object(updater, "run", return_value="97ef0d59ae475c12bac372c1f5a75cb28a854ff5\trefs/heads/feature/v5-ready")

    assert updater.get_remote_latest_commit_hash() == "97ef0d59ae475c12bac372c1f5a75cb28a854ff5"


def test_a_target_matches_despite_prefix_and_casing(mocker: MockerFixture) -> None:
    """Test that a descriptor written with 0x still targets this node"""

    trigger = _stub_compare(mocker, current="abc123", scheduled="abc123")
    mocker.patch.object(updater, "get_node_address", return_value="0x481029997EFfD67A74b48C98D763e2a2147e68A6")
    mocker.patch.object(updater, "fetch_and_parse_metadata", return_value={
        "targetNodes": [{"id": "0x481029997effd67a74b48c98d763e2a2147e68a6"}],
        "updateInAction": True,
        "updateMode": "immediate",
        "commit": "latest",
    })
    updater.set_applied_commit("older99")

    updater.compare()

    trigger.assert_called_once()


def test_a_node_outside_the_target_list_is_left_alone(mocker: MockerFixture) -> None:
    """Test that a descriptor naming other nodes does not trigger an update here"""

    trigger = _stub_compare(mocker, current="abc123", scheduled="abc123")
    mocker.patch.object(updater, "get_node_address", return_value="0xaaa")
    mocker.patch.object(updater, "fetch_and_parse_metadata", return_value={
        "targetNodes": [{"id": "0xbbb"}],
        "updateInAction": True,
        "updateMode": "immediate",
        "commit": "latest",
    })
    updater.set_applied_commit("older99")

    updater.compare()

    trigger.assert_not_called()


def test_the_checkout_lands_on_the_configured_branch(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the working copy is left on a branch rather than detached"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/feature/v5-ready:docker-compose.yml")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    checkout = next(c.args[0] for c in run.call_args_list if c.args[0][:2] == ["git", "checkout"])

    assert checkout == ["git", "checkout", "-f", "-B", "feature/v5-ready", "deadbeef"]


def test_the_checkout_falls_back_to_detached_without_a_branch(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an unreadable branch name still applies the commit"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "no-colon-here")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    mocker.patch.object(updater, "extract_branch_name", return_value=None)
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    checkout = next(c.args[0] for c in run.call_args_list if c.args[0][:2] == ["git", "checkout"])

    assert checkout == ["git", "checkout", "-f", "deadbeef"]


def test_an_update_no_longer_stashes(mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that updates leave no stash behind, since none was ever dropped"""

    monkeypatch.setenv("DOCKER_COMPOSE_REMOTE_GIT_PATH", "origin/main:docker-compose.yml")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    assert ["git", "stash"] not in [c.args[0] for c in run.call_args_list]


def test_local_modifications_are_reported_before_being_discarded(mocker: MockerFixture) -> None:
    """Test that edits about to be thrown away are named in the log and the status"""

    mocker.patch.object(updater, "run", return_value=" M nginx/conf.d/default.conf\n M docker-compose.yml")
    status = mocker.patch.object(updater, "set_status_for_ui")

    updater.report_local_modifications()

    assert "nginx/conf.d/default.conf" in status.call_args[0][0]
    assert "docker-compose.yml" in status.call_args[0][0]


def test_a_clean_tree_reports_nothing(mocker: MockerFixture) -> None:
    """Test that the usual case is silent"""

    mocker.patch.object(updater, "run", return_value="")
    status = mocker.patch.object(updater, "set_status_for_ui")

    updater.report_local_modifications()

    status.assert_not_called()


def test_nginx_is_reloaded_after_a_successful_update(mocker: MockerFixture) -> None:
    """Test that an update reloads nginx, since compose leaves a bind-mounted config alone"""

    mocker.patch.object(updater, "report_local_modifications")
    mocker.patch.object(updater, "extract_branch_name", return_value="feature/v5-ready")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "prune_images")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    mocker.patch.object(updater, "container_is_running", return_value=True)
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    commands = [c.args[0] for c in run.call_args_list]
    assert ["docker", "exec", "nginx", "nginx", "-t"] in commands
    assert ["docker", "exec", "nginx", "nginx", "-s", "reload"] in commands


def test_the_reload_happens_after_the_containers_are_up(mocker: MockerFixture) -> None:
    """Test ordering, so a reload never races a container that is still starting"""

    mocker.patch.object(updater, "report_local_modifications")
    mocker.patch.object(updater, "extract_branch_name", return_value="feature/v5-ready")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "prune_images")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    mocker.patch.object(updater, "container_is_running", return_value=True)
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    commands = [c.args[0] for c in run.call_args_list]
    up = next(i for i, c in enumerate(commands) if "up" in c and "-d" in c)
    reload_at = commands.index(["docker", "exec", "nginx", "nginx", "-s", "reload"])
    assert up < reload_at


def test_an_invalid_nginx_config_is_reported_and_not_reloaded(mocker: MockerFixture) -> None:
    """Test that a broken config leaves the last good one serving, and says so"""

    mocker.patch.object(updater, "container_is_running", return_value=True)
    error = mocker.patch.object(updater, "set_error")
    run = mocker.patch.object(
        updater,
        "run",
        side_effect=CommandError(["docker", "exec", "nginx", "nginx", "-t"], 1, "unknown directive"),
    )

    updater.reload_nginx()

    assert ["docker", "exec", "nginx", "nginx", "-s", "reload"] not in [c.args[0] for c in run.call_args_list]
    assert "unknown directive" in error.call_args[0][0]


def test_a_failed_reload_is_reported(mocker: MockerFixture) -> None:
    """Test that a reload that does not take is surfaced rather than swallowed"""

    mocker.patch.object(updater, "container_is_running", return_value=True)
    error = mocker.patch.object(updater, "set_error")

    def fail_on_reload(command: list[str], *args: object, **kwargs: object) -> str:
        if "reload" in command:
            raise CommandError(command, 1, "signal process failed")
        return ""

    mocker.patch.object(updater, "run", side_effect=fail_on_reload)

    updater.reload_nginx()

    assert "signal process failed" in error.call_args[0][0]


def test_a_missing_nginx_is_reported_distinctly(mocker: MockerFixture) -> None:
    """Test that nginx being down is not confused with a reload that failed"""

    mocker.patch.object(updater, "container_is_running", return_value=False)
    error = mocker.patch.object(updater, "set_error")
    run = mocker.patch.object(updater, "run", return_value="")

    updater.reload_nginx()

    run.assert_not_called()
    assert "not running" in error.call_args[0][0]


def test_a_reload_failure_does_not_fail_the_update(mocker: MockerFixture) -> None:
    """Test that a failed reload still records the commit.

    Raising here would leave applied_commit.json behind, and the next poll would retry
    the whole update - docker compose pull included - every minute.
    """

    mocker.patch.object(updater, "report_local_modifications")
    mocker.patch.object(updater, "extract_branch_name", return_value="feature/v5-ready")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "prune_images")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    mocker.patch.object(updater, "container_is_running", return_value=False)
    mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    assert updater.get_applied_commit() == "deadbeef"


def test_an_update_builds_images_from_source(mocker: MockerFixture) -> None:
    """Test that services with a build section are rebuilt, since pull skips them"""

    mocker.patch.object(updater, "report_local_modifications")
    mocker.patch.object(updater, "extract_branch_name", return_value="feature/v5-ready")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "prune_images")
    mocker.patch.object(updater, "reload_nginx")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    run = mocker.patch.object(updater, "run", return_value="")

    updater.trigger_update("deadbeef")

    docker_steps = [call.args[0] for call in run.call_args_list if call.args[0][0] == "docker"]

    build = next(i for i, step in enumerate(docker_steps) if step[-1] == "build")
    up = next(i for i, step in enumerate(docker_steps) if "--remove-orphans" in step)

    assert build < up


def test_a_failed_build_is_reported_but_does_not_stop_the_update(mocker: MockerFixture) -> None:
    """Test that a broken logger build still lets the validator images update.

    Raising would also leave applied_commit.json behind, and the next poll would retry
    the whole update - docker compose pull included - every minute.
    """

    mocker.patch.object(updater, "report_local_modifications")
    mocker.patch.object(updater, "extract_branch_name", return_value="feature/v5-ready")
    mocker.patch.object(updater, "ensure_disk_headroom")
    mocker.patch.object(updater, "prune_images")
    mocker.patch.object(updater, "reload_nginx")
    mocker.patch.object(updater, "get_current_git_commit_hash", return_value="deadbeef")
    error = mocker.patch.object(updater, "set_error")

    def fail_on_build(command: list[str], *args: object, **kwargs: object) -> str:
        if command[-1] == "build":
            raise CommandError(command, 1, "tsc: error TS2304")
        return ""

    run = mocker.patch.object(updater, "run", side_effect=fail_on_build)

    updater.trigger_update("deadbeef")

    assert "tsc: error TS2304" in error.call_args[0][0]
    # The update carried on, and the commit was still recorded.
    assert any("--remove-orphans" in call.args[0] for call in run.call_args_list)
    assert updater.get_applied_commit() == "deadbeef"
