"""poll state tests - what run-control.sh records about the poll itself"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import poll_state


@pytest.fixture(autouse=True)
def isolated_poll_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(poll_state, "poll_state_file", str(tmp_path / "poll.state"))
    monkeypatch.setattr(poll_state, "poll_kills_file", str(tmp_path / "poll.kills"))


def test_a_node_that_has_never_skipped_reports_zeroes() -> None:
    """Test that a missing state file is the healthy case, not an error"""

    assert poll_state.get_poll_report() == {
        "ConsecutiveSkips": 0,
        "TotalSkips": 0,
        "LastSkipAt": "",
        "LongestHeldSeconds": 0,
        "Kills": 0,
    }


def test_the_shell_format_is_read_back() -> None:
    """Test the key=value file run-control.sh actually writes"""

    Path(poll_state.poll_state_file).write_text(
        "consecutive_skips=2\ntotal_skips=37\nlast_skip_at=2026-10-01T12:40:02.000Z\nlongest_held_seconds=611\n",
        encoding="utf8",
    )
    Path(poll_state.poll_kills_file).write_text("1\n", encoding="utf8")

    report = poll_state.get_poll_report()

    assert report["ConsecutiveSkips"] == 2
    assert report["TotalSkips"] == 37
    assert report["LastSkipAt"] == "2026-10-01T12:40:02.000Z"
    assert report["LongestHeldSeconds"] == 611
    assert report["Kills"] == 1


def test_a_corrupt_state_file_cannot_take_the_poll_down() -> None:
    """Test that garbage reports zeroes rather than raising, like every other marker here"""

    Path(poll_state.poll_state_file).write_text("not key=value at all\n\x00\n", encoding="utf8")

    assert poll_state.get_poll_report()["ConsecutiveSkips"] == 0


def test_non_numeric_values_fall_back_rather_than_raising() -> None:
    """Test that a half-written file is survivable"""

    Path(poll_state.poll_state_file).write_text("consecutive_skips=\ntotal_skips=abc\n", encoding="utf8")

    report = poll_state.get_poll_report()

    assert report["ConsecutiveSkips"] == 0
    assert report["TotalSkips"] == 0


def test_a_run_of_skips_is_logged(mocker: MockerFixture) -> None:
    """Test that a poll which keeps being skipped says so, since nothing else would"""

    Path(poll_state.poll_state_file).write_text("consecutive_skips=4\n", encoding="utf8")
    info = mocker.patch.object(poll_state.logger, "info")

    poll_state.get_poll_report()

    assert "4 consecutive polls skipped" in info.call_args[0][0]
