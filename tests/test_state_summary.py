from meshdash.state_summary import (
    apply_node_saved_counts,
    build_summary_payload,
    collect_local_state_safe,
    modem_preset_from_local_state,
)
from meshdash.revision import RevisionInfo
from meshdash.tracker_snapshot_contracts import TrackerSnapshot


def test_apply_node_saved_counts_merges_stats_into_rows():
    rows = [
        {"id": "!a"},
        {"id": "!b"},
    ]
    counts = {
        "!a": {"saved_packets": 5, "saved_points": 2, "saved_last_seen": "2026-02-22 00:00:00Z"},
    }
    apply_node_saved_counts(rows, counts)

    assert rows[0]["saved_packets"] == 5
    assert rows[0]["saved_points"] == 2
    assert rows[0]["saved_last_seen"] == "2026-02-22 00:00:00Z"
    assert rows[1]["saved_packets"] == 0
    assert rows[1]["saved_points"] == 0
    assert rows[1]["saved_last_seen"] is None


def test_collect_local_state_safe_returns_error_on_exception():
    state, error = collect_local_state_safe(
        object(),
        collect_local_state_fn=lambda iface: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    assert state == {}
    assert error == "boom"


def test_modem_preset_from_local_state_handles_missing_fields():
    assert modem_preset_from_local_state({}) is None
    assert modem_preset_from_local_state({"local_config": {"lora": {"modem_preset": "LONG_FAST"}}}) == "LONG_FAST"


def test_build_summary_payload_uses_injected_time_and_disk_info():
    summary = build_summary_payload(
        target="192.168.1.109:4403 (tcp)",
        started_at=10.0,
        node_rows=[{"id": "!a"}, {"id": "!b"}],
        nodes_with_position=1,
        tracker_data=TrackerSnapshot(
            live_packet_count=4,
            real_edge_count=1,
            edges=[{"from": "!a", "to": "!b", "count": 1}],
            port_counts=[],
            recent_packets=[{"packet": {"id": 1}}],
            recent_chat=[],
        ),
        storage_probe_path=".",
        revision_info={"version": "0.1.0", "commit": "abc123"},
        modem_preset="MEDIUM_FAST",
        now_ts_fn=lambda: 35.0,
        disk_space_info_fn=lambda path: {"free_percent": 80.0},
    )

    assert summary["uptime_seconds"] == 25
    assert summary["node_count"] == 2
    assert summary["nodes_with_position"] == 1
    assert summary["live_packet_count"] == 4
    assert summary["edge_count"] == 1
    assert summary["recent_packet_buffer"] == 1
    assert summary["modem_preset"] == "MEDIUM_FAST"
    assert summary["disk"]["free_percent"] == 80.0


def test_build_summary_payload_accepts_revision_info_contract():
    summary = build_summary_payload(
        target="target",
        started_at=100.0,
        node_rows=[],
        nodes_with_position=0,
        tracker_data=TrackerSnapshot(
            live_packet_count=0,
            real_edge_count=0,
            edges=[],
            port_counts=[],
            recent_packets=[],
            recent_chat=[],
        ),
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc123", label="L", title="T"),
        modem_preset=None,
        now_ts_fn=lambda: 100.0,
        disk_space_info_fn=lambda _path: {"free_percent": "n/a"},
    )

    assert summary["revision"]["version"] == "0.1.0"
    assert summary["revision"]["commit"] == "abc123"
