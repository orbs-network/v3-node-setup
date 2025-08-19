from typing import TypedDict


class Status(TypedDict):
    """Corresponds to v2 status object"""

    Timestamp: str
    Status: str
    Error: str
    Payload: dict


class Payload(TypedDict):
    """Further breakdown of the status object"""

    Metrics: dict
    Services: dict
