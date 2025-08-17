"""SystemMonitor class tests"""

import sys
import os

from system_monitor import SystemMonitor
import json


def test_get_initial_response(mocker):
    """Test that the initial get() response returns the correct values"""

    system_monitor = SystemMonitor(client=mocker.Mock())

    status = system_monitor.get()

    assert status["Timestamp"] == ""
    assert status["Status"] == ""
    assert status["Error"] == ""
    assert status["Payload"] == {"Metrics": {}, "Services": {}}
