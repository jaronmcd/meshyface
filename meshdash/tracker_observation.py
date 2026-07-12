from .runtime_types import (
    ApplyRoutingDeliveryUpdateFn,
    DirectEdgeKeys,
    ExtractDeliveryUpdateFn,
    PortCounter,
    RecordDirectEdgeObservationFn,
    SetDeliveryStateFn,
    TrackerEdgeMap,
    TrackerParsedPacket,
)


MAX_TRACKED_PORTNUMS = 512


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
) -> DirectEdgeKeys:
    decoded = parsed["decoded"]
    from_id = parsed["from_id"]
    to_id = parsed["to_id"]
    rx_time = parsed["rx_time"]
    hops = parsed["hops"]
    portnum = parsed["portnum"]
    rx_snr = parsed.get("rx_snr")
    rx_rssi = parsed.get("rx_rssi")

    apply_routing_delivery_update_fn(
        decoded,
        from_id=from_id,
        to_id=to_id,
        extract_update_fn=extract_update_fn,
        set_delivery_state_fn=set_delivery_state_fn,
    )
    if portnum is not None:
        key = str(portnum)
        if len(key) <= 64 and (key in port_counts or len(port_counts) < MAX_TRACKED_PORTNUMS):
            port_counts[key] = int(port_counts.get(key, 0)) + 1

    direct_keys: list[tuple[str, str]] = []
    direct_key = record_direct_edge_observation_fn(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id=from_id,
        to_id=to_id,
        rx_time=rx_time,
        portnum=portnum,
        hops=hops,
        rx_snr=rx_snr,
        rx_rssi=rx_rssi,
        include_live_count=include_live_count,
    )
    if direct_key is not None:
        direct_keys.append(direct_key)
    for edge in parsed.get("neighbor_info_edges") or []:
        if not isinstance(edge, dict):
            continue
        neighbor_key = record_direct_edge_observation_fn(
            session_edges=session_edges,
            historical_edges=historical_edges,
            from_id=edge.get("from_id"),
            to_id=edge.get("to_id"),
            rx_time=edge.get("rx_time"),
            portnum=portnum,
            hops=0,
            rx_snr=edge.get("rx_snr"),
            rx_rssi=None,
            include_live_count=include_live_count,
        )
        if neighbor_key is not None:
            direct_keys.append(neighbor_key)
    return tuple(dict.fromkeys(direct_keys))
