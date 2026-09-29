"""SystemMonitor class tests"""

from docker import errors
from pytest_mock import MockerFixture

from system_monitor import SystemMonitor


def _container(mocker: MockerFixture, name: str, image_ref: str, repo_digests: object) -> object:
    """Builds a container stub carrying the attributes _get_docker_service_info reads"""

    container = mocker.Mock()
    container.name = name
    container.attrs = {
        "Image": "sha256:imageid",
        "Config": {"Image": image_ref, "Cmd": ["npm", "start"], "Env": []},
        "Created": "2026-01-01T00:00:00Z",
        "State": {
            "FinishedAt": "",
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": False,
            "Pid": 1,
            "ExitCode": 0,
            "Error": "",
        },
    }

    if isinstance(repo_digests, Exception):
        type(container).image = mocker.PropertyMock(side_effect=repo_digests)
    else:
        container.image.attrs = {"RepoDigests": repo_digests}

    return container


def test_get_initial_response(mocker: MockerFixture) -> None:
    """Test that the initial get() response returns the correct values"""

    system_monitor = SystemMonitor(client=mocker.Mock())

    status = system_monitor.get()

    assert status == {
        "Timestamp": "",
        "Status": "",
        "Error": "",
        "Extra": "",
        "Payload": {
            "Version": {"Semantic": ""},
            "Identity": {"NodeAddress": ""},
            "Metrics": {},
            "Services": {},
            "ImageDrift": [],
        },
    }


def test_service_info_reports_the_image_tag_and_digest(mocker: MockerFixture) -> None:
    """Test that each service carries the tag it runs and that image's digest"""

    client = mocker.Mock()
    client.containers.list.return_value = [
        _container(mocker, "ethereum-reader", "example/management-service:v2.7.1", ["example/management-service@sha256:abc123"]),
    ]

    services = SystemMonitor(client=client)._get_docker_service_info()

    assert services[0]["ImageTag"] == "example/management-service:v2.7.1"
    assert services[0]["ImageDigest"] == "sha256:abc123"


def test_locally_built_images_report_no_digest(mocker: MockerFixture) -> None:
    """Test that an image never pulled from a registry reports an empty digest"""

    client = mocker.Mock()
    client.containers.list.return_value = [_container(mocker, "logger", "v3-node-setup-logger", [])]

    services = SystemMonitor(client=client)._get_docker_service_info()

    assert services[0]["ImageTag"] == "v3-node-setup-logger"
    assert services[0]["ImageDigest"] == ""


def test_a_deleted_image_does_not_break_the_report(mocker: MockerFixture) -> None:
    """Test that an image removed while its container runs still yields a service entry"""

    client = mocker.Mock()
    client.containers.list.return_value = [_container(mocker, "nginx", "nginx:latest", errors.ImageNotFound("gone"))]

    services = SystemMonitor(client=client)._get_docker_service_info()

    assert services[0]["ImageTag"] == "nginx:latest"
    assert services[0]["ImageDigest"] == ""


def test_node_address_gets_the_missing_prefix(mocker: MockerFixture, monkeypatch) -> None:
    """Test that the address stored without 0x is reported with it"""

    # generate_wallet.py strips the prefix before storing, but consumers expect one.
    monkeypatch.setenv("NODE_ADDRESS", "481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert SystemMonitor(client=mocker.Mock())._get_node_address() == "0x481029997EFfD67A74b48C98D763e2a2147e68A6"


def test_node_address_keeps_an_existing_prefix(mocker: MockerFixture, monkeypatch) -> None:
    """Test that an address already carrying 0x is not given a second one"""

    monkeypatch.setenv("NODE_ADDRESS", "0xabc123")

    assert SystemMonitor(client=mocker.Mock())._get_node_address() == "0xabc123"


def test_node_address_preserves_checksum_casing(mocker: MockerFixture, monkeypatch) -> None:
    """Test that the EIP-55 mixed case is left intact"""

    monkeypatch.setenv("NODE_ADDRESS", "481029997EFfD67A74b48C98D763e2a2147e68A6")

    assert SystemMonitor(client=mocker.Mock())._get_node_address().endswith("EFfD67A74b48C98D763e2a2147e68A6")


def test_a_missing_node_address_reports_empty(mocker: MockerFixture, monkeypatch) -> None:
    """Test that an unconfigured node reports an empty address rather than raising"""

    monkeypatch.delenv("NODE_ADDRESS", raising=False)

    assert SystemMonitor(client=mocker.Mock())._get_node_address() == ""
