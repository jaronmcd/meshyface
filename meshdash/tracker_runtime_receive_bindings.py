from typing import Any

try:
    import meshtastic
except Exception:
    meshtastic = None

from .helpers import (
    to_int as _to_int,
)
from .nodes import (
    get_node_id_from_num as _get_node_id_from_num_helper,
)
from .tracker_node_resolver import (
    get_tracker_node_id_from_num as _get_tracker_node_id_from_num_helper,
)
from .tracker_runtime_receive import (
    record_tracker_receive_unlocked as _record_tracker_receive_unlocked_helper,
)
from .tracker_runtime_record import (
    record_tracker_packet_unlocked_with_dependencies as _record_tracker_packet_unlocked_with_dependencies_helper,
)
from .runtime_types import (
    GetNodeIdFromNumFn,
    RecordTrackerPacketUnlockedFn,
    RecordTrackerPacketUnlockedWithDependenciesFn,
    TrackerPacket,
)


def _resolve_tracker_node_id_from_num(
    iface: Any,
    node_num: Any,
    *,
    meshtastic_module: Any = meshtastic,
    to_int_fn: Any = _to_int,
    get_node_id_from_num_fn: Any = _get_node_id_from_num_helper,
) -> Any:
    return _get_tracker_node_id_from_num_helper(
        iface,
        node_num,
        meshtastic_module=meshtastic_module,
        to_int_fn=to_int_fn,
        get_node_id_from_num_fn=get_node_id_from_num_fn,
    )


def record_tracker_receive_unlocked_for_tracker(
    tracker: Any,
    *,
    packet: TrackerPacket,
    interface: Any,
    include_live_count: bool,
    get_node_id_from_num_fn: GetNodeIdFromNumFn = _get_node_id_from_num_helper,
    record_tracker_packet_unlocked_fn: RecordTrackerPacketUnlockedFn | None = None,
    record_tracker_packet_unlocked_with_dependencies_fn: RecordTrackerPacketUnlockedWithDependenciesFn = _record_tracker_packet_unlocked_with_dependencies_helper,
    resolve_tracker_node_id_from_num_fn: Any = _resolve_tracker_node_id_from_num,
    record_tracker_receive_unlocked_fn: Any = _record_tracker_receive_unlocked_helper,
) -> None:
    record_tracker_receive_unlocked_fn(
        tracker,
        packet=packet,
        interface=interface,
        include_live_count=include_live_count,
        get_node_id_from_num_fn=lambda iface, node_num: resolve_tracker_node_id_from_num_fn(
            iface,
            node_num,
            get_node_id_from_num_fn=get_node_id_from_num_fn,
        ),
        record_tracker_packet_unlocked_fn=record_tracker_packet_unlocked_fn,
        record_tracker_packet_unlocked_with_dependencies_fn=record_tracker_packet_unlocked_with_dependencies_fn,
    )
