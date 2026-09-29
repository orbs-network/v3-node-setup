from typing import Any, Dict, List, TypedDict


class Version(TypedDict):
    Semantic: str


class Identity(TypedDict):
    """The addresses this node runs as"""

    NodeAddress: str


class Payload(TypedDict):
    """Further breakdown of the status object"""

    Version: Version
    Identity: Identity
    Metrics: Dict[str, Any]
    Services: Dict[str, Any]
    ImageDrift: List[Dict[str, Any]]


class Status(TypedDict):
    """Corresponds to v2 status object"""

    Timestamp: str
    Status: str
    Error: str
    Extra: str
    Payload: Payload
