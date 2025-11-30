"""SystemMonitor class tests"""

from pytest_mock import MockerFixture

from system_monitor import SystemMonitor


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
            "Metrics": {},
            "Services": {},
        },
    }
