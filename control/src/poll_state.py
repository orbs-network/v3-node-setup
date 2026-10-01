"""What the poll itself did, as recorded by run-control.sh.

Control cannot observe any of this from the inside. It only ever runs while holding the
poll lock, so it would always see "held by me" and would never see the ticks that were
skipped waiting for a long update, or the ones that gave up and killed it. The shell
writes those facts down; this reads them back.

Plain `key=value` rather than JSON, because the shell writes it before the venv is
guaranteed to exist and has no business depending on a JSON tool to do it.
"""

from config import poll_kills_file, poll_state_file
from logger import logger


def _read_pairs(path):
    try:
        with open(path, "r", encoding="utf8") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return {}

    pairs = {}
    for line in lines:
        key, separator, value = line.partition("=")
        if separator:
            pairs[key.strip()] = value.strip()
    return pairs


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_poll_report():
    """Facts about the poll itself. Zeroes on a node that has never skipped a tick."""

    pairs = _read_pairs(poll_state_file)

    try:
        with open(poll_kills_file, "r", encoding="utf8") as handle:
            kills = _as_int(handle.read().strip())
    except OSError:
        kills = 0

    report = {
        # Skips in an unbroken run, cleared the moment a poll takes the lock. This is the
        # one that says whether something is wrong *now*.
        "ConsecutiveSkips": _as_int(pairs.get("consecutive_skips")),
        # Never cleared, so it survives the problem passing.
        "TotalSkips": _as_int(pairs.get("total_skips")),
        "LastSkipAt": pairs.get("last_skip_at", ""),
        "LongestHeldSeconds": _as_int(pairs.get("longest_held_seconds")),
        # Times a wedged poll had to be killed. Capped in the shell, after which it reports
        # rather than killing, so this stops rising while the problem does not.
        "Kills": kills,
    }

    if report["ConsecutiveSkips"]:
        logger.info(
            f"{report['ConsecutiveSkips']} consecutive polls skipped - a previous one is still running"
        )

    return report
