from collections.abc import Iterable

from .tracker_snapshot_build_contracts import EdgeKey, EdgeRow


def build_historical_edges(
    connection_rows: Iterable[EdgeRow],
) -> dict[EdgeKey, EdgeRow]:
    out: dict[EdgeKey, EdgeRow] = {}
    for edge in connection_rows:
        from_id = str(edge["from"])
        to_id = str(edge["to"])
        key = (from_id, to_id)
        out[key] = {
            "from": from_id,
            "to": to_id,
            "count": int(edge["count"]),
            "first_rx_time": edge.get("first_rx_time"),
            "last_rx_time": edge.get("last_rx_time"),
            "portnums": set(edge.get("portnums") or []),
            "last_hops": edge.get("last_hops"),
            "hops_sum": int(edge.get("hops_sum") or 0),
            "hops_count": int(edge.get("hops_count") or 0),
        }
    return out
