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
            "Identity": {"NodeAddress": "", "EthAddress": "", "Registration": "unknown"},
            "Metrics": {},
            "Services": {},
            "ImageDrift": [],
            "StaleComponents": [],
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


def _disk(mount: str, percent: float, fstype: str = "ext4") -> dict:
    return {"Mountpoint": mount, "Fstype": fstype, "UsedPercent": percent, "TotalMbytes": 1.0, "UsedMbytes": 1.0}


def test_snap_mounts_never_raise_the_alarm(mocker: MockerFixture) -> None:
    """Test that permanently full pseudo filesystems are ignored"""

    # Six of the nine mounts on these nodes are squashfs snap images sitting at 100%.
    # Alerting on those would fire on every node forever.
    status = mocker.patch("system_monitor.set_status_for_ui")

    SystemMonitor(client=mocker.Mock())._check_disk_usage([
        _disk("/snap/core22/2437", 100.0, "squashfs"),
        _disk("/snap/snapd/27710", 100.0, "squashfs"),
        _disk("/", 43.5),
    ])

    status.assert_not_called()


def test_a_filling_disk_warns(mocker: MockerFixture, monkeypatch) -> None:
    """Test that crossing the warn threshold reaches the status line"""

    monkeypatch.setenv("DISK_WARN_PERCENT", "80")
    monkeypatch.setenv("DISK_CRITICAL_PERCENT", "90")
    status = mocker.patch("system_monitor.set_status_for_ui")
    error = mocker.patch("system_monitor.set_error")

    SystemMonitor(client=mocker.Mock())._check_disk_usage([_disk("/", 84.0)])

    assert "84% full" in status.call_args[0][0]
    error.assert_not_called()


def test_a_critical_disk_sets_the_error(mocker: MockerFixture, monkeypatch) -> None:
    """Test that crossing the critical threshold claims the error field"""

    monkeypatch.setenv("DISK_CRITICAL_PERCENT", "90")
    mocker.patch("system_monitor.set_status_for_ui")
    mocker.patch("system_monitor.get_error", return_value="")
    error = mocker.patch("system_monitor.set_error")

    SystemMonitor(client=mocker.Mock())._check_disk_usage([_disk("/", 95.0)])

    assert "95% full" in error.call_args[0][0]


def test_a_critical_disk_does_not_clobber_an_existing_error(mocker: MockerFixture, monkeypatch) -> None:
    """Test that a more specific error keeps the field"""

    # A failed update says more about what is wrong than a filling disk does.
    monkeypatch.setenv("DISK_CRITICAL_PERCENT", "90")
    mocker.patch("system_monitor.set_status_for_ui")
    mocker.patch("system_monitor.get_error", return_value="An update failed")
    error = mocker.patch("system_monitor.set_error")

    SystemMonitor(client=mocker.Mock())._check_disk_usage([_disk("/", 95.0)])

    error.assert_not_called()


def test_a_healthy_disk_is_silent(mocker: MockerFixture) -> None:
    """Test that normal usage produces nothing"""

    status = mocker.patch("system_monitor.set_status_for_ui")

    SystemMonitor(client=mocker.Mock())._check_disk_usage([_disk("/", 43.5)])

    status.assert_not_called()
