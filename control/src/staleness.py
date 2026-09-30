"""Detects components that have stopped refreshing their status file.

A container can sit at `Up 6 months (healthy)` while doing nothing useful, because Docker
only knows whether the process is alive. What a component last wrote about itself is a
better signal, and one nothing was reading.

A stale status means the component has stopped reporting, which is not the same as it
being down: it may be working perfectly and only failing to say so. The distinction
matters, so this reports staleness and draws no conclusion beyond it.
"""

import json
import os
from datetime import datetime, timezone

import yaml

from config import BASE_DIR
from logger import logger

# Every component is expected to refresh its status at least this often, whatever its own
# tick interval. One threshold for all of them: a component that cannot meet it is a bug
# to fix rather than an exception to configure.
STALE_AFTER_SECONDS = int(os.getenv("STATUS_STALE_AFTER_MINUTES", "10")) * 60

# Where a component mounts the directory it writes its status file into.
STATUS_MOUNT = "/opt/orbs/status"

FRESH = "fresh"
STALE = "stale"
UNKNOWN = "unknown"


def reporting_components(compose_file: str) -> list[str]:
    """Returns the components that are expected to write a status file.

    A component declares that by mounting a status directory, so the expectation comes
    from the compose file rather than from assuming every service reports. nginx mounts
    `.data` to *serve* those files and writes none of its own, and holding it to a
    contract it never entered would leave a permanent unknown that people learn to skip.
    """

    with open(compose_file, encoding="utf8") as file:
        compose = yaml.safe_load(file)

    names = []

    for name, service in (compose.get("services") or {}).items():
        if any(str(volume).endswith(STATUS_MOUNT) for volume in (service.get("volumes") or [])):
            names.append(service.get("container_name", name))

    return sorted(names)


def status_file_for(container_name: str) -> str:
    """Returns where a component writes the status file it is judged on"""

    return os.path.join(BASE_DIR, ".data", container_name, "status.json")


def parse_timestamp(value: str):
    """Returns the timestamp as an aware datetime, or None when it cannot be read.

    Precision is not consistent across components: milliseconds, microseconds and
    nanoseconds all appear. fromisoformat copes with 3 and 6 fractional digits but not 9,
    so the fraction is truncated before parsing.
    """

    text = str(value).strip().removesuffix("Z")

    if "." in text:
        head, _, fraction = text.partition(".")
        text = f"{head}.{fraction[:6]}"

    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None

    # The components write UTC and mark it with a trailing Z, which is stripped above.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def check(compose_file: str) -> list[dict]:
    """Returns one record per component that is not reporting freshly"""

    now = datetime.now(timezone.utc)
    reported = []

    for container_name in reporting_components(compose_file):
        record = {"Service": container_name, "Timestamp": "", "AgeSeconds": 0, "State": UNKNOWN}

        try:
            with open(status_file_for(container_name), encoding="utf8") as file:
                record["Timestamp"] = str(json.load(file).get("Timestamp", ""))
        except (OSError, ValueError) as error:
            logger.debug("No readable status for %s: %s", container_name, error)
            reported.append(record)
            continue

        written = parse_timestamp(record["Timestamp"])

        if written is None:
            # An unreadable timestamp is not the same as an old one, and must not be
            # reported as though we knew how stale it was.
            reported.append(record)
            continue

        age = (now - written).total_seconds()
        record["AgeSeconds"] = int(age)
        record["State"] = STALE if age > STALE_AFTER_SECONDS else FRESH

        if record["State"] != FRESH:
            reported.append(record)

    logger.debug("Staleness check found %d component(s) not reporting freshly", len(reported))

    return reported


def summarize(reported: list[dict]) -> str:
    """Returns a one-line summary, or an empty string when every component is fresh"""

    if not reported:
        return ""

    stale = [f"{r['Service']} {r['AgeSeconds'] // 60}m" for r in reported if r["State"] == STALE]
    unknown = [r["Service"] for r in reported if r["State"] == UNKNOWN]

    parts = []

    if stale:
        parts.append(f"{len(stale)} stale ({' '.join(stale)})")
    if unknown:
        parts.append(f"{len(unknown)} unreadable ({' '.join(unknown)})")

    # No commas: set_status_for_ui strips them, since get_status_for_ui joins entries with one.
    return "Status stale: " + " | ".join(parts)
