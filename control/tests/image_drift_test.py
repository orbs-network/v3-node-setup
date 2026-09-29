"""image_drift tests"""

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import image_drift


COMPOSE = """
services:
  ethereum-reader:
    container_name: ethereum-reader
    image: example/management-service:v2.7.1-immediate
  logger:
    container_name: logger
    build:
      context: ./logging
  unnamed-service:
    image: example/other:v1
"""


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives each test its own digest cache, so results cannot leak between them"""

    monkeypatch.setattr(image_drift, "cache_file", str(tmp_path / "image_drift.json"))


def _compose_file(tmp_path: Path) -> str:
    path = tmp_path / "docker-compose.yml"
    path.write_text(COMPOSE, encoding="utf8")
    return str(path)


def _client(mocker: MockerFixture, local_id: str, local_digest: str, registry_digest: str, container_image_id: str) -> object:
    """Builds a docker client stub with one image and one container"""

    client = mocker.Mock()
    client.images.get.return_value = mocker.Mock(id=local_id, attrs={"RepoDigests": [f"example/management-service@{local_digest}"]})
    client.images.get_registry_data.return_value = mocker.Mock(id=registry_digest)
    client.containers.get.return_value = mocker.Mock(image=mocker.Mock(id=container_image_id))

    return client


def test_compose_images_skips_locally_built_services(tmp_path: Path) -> None:
    """Test that services with a build: are left out, having no registry image to compare"""

    images = image_drift.compose_images(_compose_file(tmp_path))

    assert images == {
        "ethereum-reader": "example/management-service:v2.7.1-immediate",
        "unnamed-service": "example/other:v1",
    }


def test_compose_images_falls_back_to_the_service_name(tmp_path: Path) -> None:
    """Test that a service without container_name is keyed by its service name"""

    assert "unnamed-service" in image_drift.compose_images(_compose_file(tmp_path))


def test_no_drift_when_everything_matches(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that matching digests and a current container report no drift"""

    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:same", registry_digest="sha256:same", container_image_id="sha256:aaa")

    assert image_drift.check(client, _compose_file(tmp_path)) == []


def test_detects_image_behind_the_registry(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that a mutable tag re-pushed upstream is reported, though nothing local changed"""

    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:old", registry_digest="sha256:new", container_image_id="sha256:aaa")

    drifted = image_drift.check(client, _compose_file(tmp_path))

    assert [record["Service"] for record in drifted] == ["ethereum-reader", "unnamed-service"]
    assert drifted[0]["ImageOutdated"] is True
    assert drifted[0]["ContainerOutdated"] is False


def test_detects_container_not_recreated_after_a_pull(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that a container still running the previous image is reported"""

    client = _client(mocker, local_id="sha256:new", local_digest="sha256:same", registry_digest="sha256:same", container_image_id="sha256:old")

    drifted = image_drift.check(client, _compose_file(tmp_path))

    assert drifted[0]["ContainerOutdated"] is True
    assert drifted[0]["ImageOutdated"] is False


def test_unreadable_registry_digest_is_not_treated_as_drift(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that failing to reach the registry does not masquerade as an outdated image"""

    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:local", registry_digest="", container_image_id="sha256:aaa")
    client.images.get_registry_data.side_effect = RuntimeError("registry unreachable")

    drifted = image_drift.check(client, _compose_file(tmp_path))

    assert drifted == []


def test_summarize_avoids_commas(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that the summary carries no commas, which set_status_for_ui would strip"""

    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:old", registry_digest="sha256:new", container_image_id="sha256:aaa")

    summary = image_drift.summarize(image_drift.check(client, _compose_file(tmp_path)))

    assert "behind registry" in summary
    assert "," not in summary


def test_a_successful_refresh_is_cached(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that the registry is not queried again within the refresh interval"""

    # Querying counts against Docker Hub's anonymous pull rate limit, and the poll runs
    # every minute, so caching is what keeps this from exhausting the limit.
    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:same", registry_digest="sha256:same", container_image_id="sha256:aaa")
    compose_file = _compose_file(tmp_path)

    image_drift.check(client, compose_file)
    calls_after_first = client.images.get_registry_data.call_count

    image_drift.check(client, compose_file)

    assert client.images.get_registry_data.call_count == calls_after_first


def test_a_failed_refresh_is_retried_on_the_next_poll(tmp_path: Path, mocker: MockerFixture) -> None:
    """Test that a registry failure is retried rather than held for the refresh interval"""

    client = _client(mocker, local_id="sha256:aaa", local_digest="sha256:same", registry_digest="sha256:same", container_image_id="sha256:aaa")
    client.images.get_registry_data.side_effect = RuntimeError("registry unreachable")
    compose_file = _compose_file(tmp_path)

    image_drift.check(client, compose_file)
    calls_after_first = client.images.get_registry_data.call_count

    image_drift.check(client, compose_file)

    assert client.images.get_registry_data.call_count > calls_after_first


def test_summarize_is_empty_when_nothing_drifted() -> None:
    """Test that a clean check produces no status line"""

    assert image_drift.summarize([]) == ""
