from dataclasses import dataclass
from typing import Optional

from .revision import RevisionInfo
from .state_service_contracts import StateTracker


@dataclass(frozen=True)
class StateSnapshotRuntimeDependencies:
    iface: object
    tracker: StateTracker
    started_at: float
    target: str
    show_secrets: bool
    storage_probe_path: Optional[str]
    revision_info: RevisionInfo
