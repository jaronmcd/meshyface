from typing import Any, Protocol

from .runtime_types import (
    ExtractDeliveryUpdateFn,
    SetDeliveryStateFn,
    TrackerEdgeMap,
)


class TrackerReceiveRuntimeState(Protocol):
    edges: TrackerEdgeMap
    _historical_edges: TrackerEdgeMap
    port_counts: Any
    recent_packets: Any
    recent_chat: Any
    _history_store: Any
    _extract_delivery_update_fn: ExtractDeliveryUpdateFn
    _set_delivery_state_fn: SetDeliveryStateFn

    def _expire_pending_deliveries_fn(self) -> None:
        ...
