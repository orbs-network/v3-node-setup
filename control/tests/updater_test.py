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
    mocker.patch.object(updater, "get_guardian_node_id", return_value="node-1")
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
