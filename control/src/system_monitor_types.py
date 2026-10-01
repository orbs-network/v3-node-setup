from typing import Any, Dict, List, TypedDict


class Version(TypedDict):
    Semantic: str


class Identity(TypedDict):
    """The addresses this node runs as"""

    NodeAddress: str
    EthAddress: str
    Registration: str


class Updater(TypedDict):
    """What the updater did, as facts rather than prose.

    Previously the only way to answer "is this node up to date" was to read the joined
    status string, which mixes update state with everything else control reports.
    """

    Branch: str
    AppliedCommit: str
    AppliedAt: str
    CheckedOutCommit: str
    # The commit whose updater code ran. An update is applied by the code from the previous
    # commit, so this differs from CheckedOutCommit on the tick that applies one.
    RunningCommit: str
    TargetCommit: str
    State: str
    ScheduledFor: int
    UpdatesDisabled: bool
    LastAttemptAt: str
    LastSuccessAt: str
    LastError: str
    ConsecutiveFailures: int


class Payload(TypedDict):
    """Further breakdown of the status object"""

    Version: Version
    Identity: Identity
    Metrics: Dict[str, Any]
    Services: Dict[str, Any]
    ImageDrift: List[Dict[str, Any]]
    StaleComponents: List[Dict[str, Any]]
    Updater: Updater


class Status(TypedDict):
    """Corresponds to v2 status object"""

    Timestamp: str
    Status: str
    Error: str
    Extra: str
    Payload: Payload
