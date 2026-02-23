from meshdash.tracker_snapshot import build_edge_snapshot_rows


def _fmt_epoch(value):
    return None if value is None else f"t{int(value)}"


def test_build_edge_snapshot_rows_merges_session_and_historical_values():
    session_edges = {
        ("!a", "!b"): {
            "count": 2,
            "first_rx_time": 110,
            "last_rx_time": 130,
            "portnums": {"TEXT_MESSAGE_APP"},
            "last_hops": 3,
            "hops_sum": 5,
            "hops_count": 2,
        }
    }
    historical_edges = {
        ("!a", "!b"): {
            "count": 5,
            "first_rx_time": 100,
            "last_rx_time": 120,
            "portnums": {"NODEINFO_APP"},
            "last_hops": 2,
            "hops_sum": 10,
            "hops_count": 4,
        }
    }

    rows, real_count = build_edge_snapshot_rows(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id={},
        min_real_link_count=2,
        format_epoch_fn=_fmt_epoch,
    )

    assert real_count == 1
    assert len(rows) == 1
    row = rows[0]
    assert row["from"] == "!a"
    assert row["to"] == "!b"
    assert row["session_count"] == 2
    assert row["lifetime_count"] == 5
    assert row["is_real"] is True
    assert row["first_rx_time"] == "t100"
    assert row["last_rx_time"] == "t130"
    assert row["portnums"] == ["NODEINFO_APP", "TEXT_MESSAGE_APP"]
    assert row["last_hops"] == 2
    assert row["avg_hops"] == 2.5
    assert row["hops_samples"] == 4


def test_build_edge_snapshot_rows_adds_geo_fields_for_session_only_edges():
    session_edges = {
        ("!x", "!y"): {
            "count": 1,
            "first_rx_time": 50,
            "last_rx_time": 60,
            "portnums": {"TEXT_MESSAGE_APP"},
            "last_hops": 1,
            "hops_sum": 1,
            "hops_count": 1,
        }
    }
    nodes_by_id = {
        "!x": {"lat": 44.95, "lon": -93.1},
        "!y": {"lat": 45.00, "lon": -93.2},
    }

    rows, real_count = build_edge_snapshot_rows(
        session_edges=session_edges,
        historical_edges={},
        nodes_by_id=nodes_by_id,
        min_real_link_count=2,
        format_epoch_fn=_fmt_epoch,
    )

    assert real_count == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["is_real"] is False
    assert row["confidence"] == "observed"
    assert row["src_lat"] == 44.95
    assert row["src_lon"] == -93.1
    assert row["dst_lat"] == 45.0
    assert row["dst_lon"] == -93.2
