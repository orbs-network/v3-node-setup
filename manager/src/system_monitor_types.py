from typing import TypedDict

class Version(TypedDict):
    Semantic: str

class Status(TypedDict):
    """Corresponds to v2 status object"""

    Timestamp: str
    Status: str
    Error: str
    Extra : str
    Payload: dict


class Payload(TypedDict):
    """Further breakdown of the status object"""
    Version : dict
    Metrics: dict
    Services: dict
