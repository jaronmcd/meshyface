from .runtime_types import (
    ApplyRoutingDeliveryUpdateFn,
    DirectEdgeKey,
    ExtractDeliveryUpdateFn,
    PortCounter,
    RecordDirectEdgeObservationFn,
    SetDeliveryStateFn,
    TrackerEdgeMap,
    TrackerParsedPacket,
)


def apply_tracker_observation(
    *,
    parsed: TrackerParsedPacket,
    include_live_count: bool,
    session_edges: TrackerEdgeMap,
    historical_edges: TrackerEdgeMap,
    port_counts: PortCounter,
    apply_routing_delivery_update_fn: ApplyRoutingDeliveryUpdateFn,
    extract_update_fn: ExtractDeliveryUpdateFn,
    set_delivery_state_fn: SetDeliveryStateFn,
    record_direct_edge_observation_fn: RecordDirectEdgeObservationFn,
) -> DirectEdgeKey:
    decoded = parsed["decoded"]
    from_id = parsed["from_id"]
    to_id = parsed["to_id"]
    rx_time = parsed["rx_time"]
    hops = parsed["hops"]
    portnum = parsed["portnum"]

    apply_routing_delivery_update_fn(
        decoded,
        extract_update_fn=extract_update_fn,
        set_delivery_state_fn=set_delivery_state_fn,
    )
    if portnum is not None:
        key = str(portnum)
        port_counts[key] = int(port_counts.get(key, 0)) + 1

    return record_direct_edge_observation_fn(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id=from_id,
        to_id=to_id,
        rx_time=rx_time,
        portnum=portnum,
        hops=hops,
        include_live_count=include_live_count,
    )
