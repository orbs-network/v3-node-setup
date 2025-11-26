from typing import Any, Dict, TypedDict


class Version(TypedDict):
    Semantic: str


class Payload(TypedDict):
    """Further breakdown of the status object"""

    Version: Version
    Metrics: Dict[str, Any]
    Services: Dict[str, Any]


class Status(TypedDict):
    """Corresponds to v2 status object"""

    Timestamp: str
    Status: str
    Error: str
    Extra: str
    Payload: Payload
