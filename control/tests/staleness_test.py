"""staleness tests"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import staleness

COMPOSE = """
services:
  ethereum-reader:
    container_name: ethereum-reader
    image: example/reader:v1
  vm-lambda:
    container_name: vm-lambda
    image: example/lambda:v1
  logger:
    build:
      context: ./logging
"""


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the checker at a .data tree this test controls"""

    monkeypatch.setattr(staleness, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(staleness, "status_file_for", lambda name: str(tmp_path / ".data" / name / "status.json"))

    return tmp_path


def _compose(tmp_path: Path) -> str:
    path = tmp_path / "docker-compose.yml"
    path.write_text(COMPOSE, encoding="utf8")
    return str(path)


def _write_status(tmp_path: Path, name: str, timestamp: str) -> None:
    path = tmp_path / ".data" / name / "status.json"
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(json.dumps({"Timestamp": timestamp}), encoding="utf8")


def _iso(minutes_ago: float, fraction_digits: int = 3) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond:06d}"[:fraction_digits].ljust(fraction_digits, "0") + "Z"


def test_milliseconds_parse() -> None:
    """Test that the common millisecond form is understood"""

    assert staleness.parse_timestamp("2026-09-29T13:25:01.776Z") is not None


def test_microseconds_parse() -> None:
    """Test that the microsecond form vm-l3-dummy-service writes is understood"""

    assert staleness.parse_timestamp("2026-09-29T13:25:24.044297Z") is not None


def test_nanoseconds_parse() -> None:
    """Test that the nanosecond form signer and vm-verifier write is understood"""

    # fromisoformat rejects 9 fractional digits outright, so the fraction is truncated.
    assert staleness.parse_timestamp("2026-09-29T13:25:15.347422897Z") is not None


def test_a_parsed_timestamp_is_utc() -> None:
    """Test that a timestamp with no offset is read as UTC, not as local time"""

    # The components write UTC and mark it with a trailing Z. Reading it as local time
    # would shift every age by the node's offset.
    assert staleness.parse_timestamp("2026-09-29T13:25:01.776Z").tzinfo == timezone.utc


def test_an_unparseable_timestamp_returns_nothing() -> None:
    """Test that nonsense is rejected rather than guessed at"""

    assert staleness.parse_timestamp("not a timestamp") is None


def test_fresh_components_are_not_reported(tmp_path: Path) -> None:
    """Test that components reporting within the threshold stay quiet"""

    _write_status(tmp_path, "ethereum-reader", _iso(1))
    _write_status(tmp_path, "vm-lambda", _iso(5))

    reported = staleness.check(_compose(tmp_path))

    assert [r["Service"] for r in reported] == ["logger"]  # only the one with no status file


def test_a_stale_component_is_reported(tmp_path: Path) -> None:
    """Test that a status older than the threshold is flagged"""

    _write_status(tmp_path, "ethereum-reader", _iso(1))
    _write_status(tmp_path, "vm-lambda", _iso(200_000))  # months, as seen on the real nodes
    _write_status(tmp_path, "logger", _iso(1))

    stale = [r for r in staleness.check(_compose(tmp_path)) if r["State"] == staleness.STALE]

    assert [r["Service"] for r in stale] == ["vm-lambda"]
    assert stale[0]["AgeSeconds"] > staleness.STALE_AFTER_SECONDS


def test_a_missing_status_file_is_unknown_not_stale(tmp_path: Path) -> None:
    """Test that never having reported is distinguished from having stopped"""

    _write_status(tmp_path, "ethereum-reader", _iso(1))
    _write_status(tmp_path, "logger", _iso(1))

    reported = staleness.check(_compose(tmp_path))

    assert [(r["Service"], r["State"]) for r in reported] == [("vm-lambda", staleness.UNKNOWN)]


def test_an_unreadable_timestamp_is_unknown(tmp_path: Path) -> None:
    """Test that a status we cannot date is not reported as a specific age"""

    _write_status(tmp_path, "ethereum-reader", "garbage")
    _write_status(tmp_path, "vm-lambda", _iso(1))
    _write_status(tmp_path, "logger", _iso(1))

    reported = staleness.check(_compose(tmp_path))

    assert reported[0]["Service"] == "ethereum-reader"
    assert reported[0]["State"] == staleness.UNKNOWN
    assert reported[0]["AgeSeconds"] == 0


def test_locally_built_services_are_included(tmp_path: Path) -> None:
    """Test that a service without an image is still expected to report"""

    # Unlike the drift check, staleness applies to every component, built or pulled.
    assert "logger" in staleness.compose_container_names(_compose(tmp_path))


def test_summarize_avoids_commas(tmp_path: Path) -> None:
    """Test that the summary carries no commas, which set_status_for_ui would strip"""

    _write_status(tmp_path, "ethereum-reader", _iso(1))
    _write_status(tmp_path, "vm-lambda", _iso(200_000))
    _write_status(tmp_path, "logger", _iso(1))

    summary = staleness.summarize(staleness.check(_compose(tmp_path)))

    assert "vm-lambda" in summary
    assert "," not in summary


def test_summarize_is_empty_when_all_fresh() -> None:
    """Test that a clean check produces no status line"""

    assert staleness.summarize([]) == ""
