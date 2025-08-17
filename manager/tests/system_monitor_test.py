"""SystemMonitor class tests"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from system_monitor import SystemMonitor
import json


def test_get_initial_response(mocker):
    """Test that the initial get() response returns the correct values"""

    system_monitor = SystemMonitor(client=mocker.Mock())

    status = system_monitor.get()

    print("--------------------------------")
    print(json.dumps(status, indent=2))
    print("--------------------------------")

    assert status["Timestamp"] == ""
    assert status["Status"] == ""
    assert status["Error"] == ""
    assert status["Payload"] == {"Metrics": {}, "Services": {}}
