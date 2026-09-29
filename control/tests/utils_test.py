"""utils.run tests"""

import pytest

from utils import CommandError, run


def test_run_returns_stdout() -> None:
    """Test that a successful command returns its stdout"""

    assert run(["echo", "hello"]) == "hello"


def test_run_tolerates_stderr_on_success() -> None:
    """Test that output on stderr alone is not treated as a failure"""

    # docker compose reports its normal progress on stderr, so treating that as an error
    # would make every successful update look broken.
    assert run(["sh", "-c", "echo progress >&2; echo done"]) == "done"


def test_run_raises_on_failure() -> None:
    """Test that a failing command raises, carrying its exit status and stderr"""

    with pytest.raises(CommandError) as excinfo:
        run(["sh", "-c", "echo boom >&2; exit 2"])

    assert excinfo.value.returncode == 2
    assert "boom" in excinfo.value.output


def test_run_without_check_returns_instead_of_raising() -> None:
    """Test that a failing command returns its stdout when check is disabled"""

    assert run(["sh", "-c", "echo out; exit 3"], check=False) == "out"
