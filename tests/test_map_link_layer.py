import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_readers import decode_connections_rows
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell
from meshdash.tracker_edges import record_direct_edge_observation
from meshdash.tracker_history_edges import build_historical_edges
from meshdash.tracker_snapshot import build_edge_snapshot_rows


def test_dashboard_html_adds_map_link_layer_toggle() -> None:
    html = build_html_shell(
        app_title="Meshyface",
        app_heading="Meshyface",
        style_css="",
        app_js="",
        revision_title="rev",
        revision_label="rev",
        safety_label="safe",
        packet_limit=100,
        history_label="history",
        refresh_ms=1000,
    )

    assert 'id="map-link-wrap"' in html
    assert 'id="map-link-toggle"' in html
    assert "Link Layer" in html


def test_dashboard_js_supports_map_link_layer_overlay() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'let mapLinkLayerEnabled = false;' in js
    assert 'const mapLinkLayerStorageKey = "meshDashboardMapLinkLayerEnabledV1";' in js
    assert "function updateMapLinkLayerControl()" in js
    assert "function bindMapLinkLayerControl()" in js
    assert "function estimatedMarkerStyle(isSelected, confidence = 0.5)" in js
    assert "function buildMapLinkLayerOverlay(nodes, rawEdges)" in js
    assert "nodeMarkerKinds" in js
    assert "nodeMarkerConfidence" in js
    assert "linkEstimateLayer" in js
    assert "estimateLine && estimateLine.avgHops ??" not in js
    assert "estimateLine && estimateLine.avgSnr ??" not in js
    assert "estimateLine && estimateLine.avgRssi ??" not in js


def test_dashboard_js_keeps_leaflet_tile_layers_removable_on_theme_swap() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "mapTileLayer.off();" not in js
    assert "settingsFixedMapTileLayer.off();" not in js


def test_dashboard_js_packet_line_fade_tracks_node_freshness_windows() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "const onlineWindowSec = Math.max(0, Number(chatWarnWindowSeconds) || (10 * 60));" in js
    assert "const staleWindowSec = Math.max(" in js
    assert "Number(chatStaleWindowSeconds) || (30 * 60)" in js
    assert "const fadeStartSec = 45 * 60;" not in js
    assert "const fadeFullSec = 24 * 60 * 60;" not in js
    assert "const minOpacity = isReal ? 0.56 : 0.44;" in js
    assert "Math.max(isReal ? 2.2 : 1.7, baseWeight * 0.62)" in js
    assert 'lineCap: "round"' in js
    assert 'lineJoin: "round"' in js


def test_record_direct_edge_observation_tracks_signal_metrics() -> None:
    session_edges: dict[tuple[str, str], dict[str, object]] = {}
    historical_edges: dict[tuple[str, str], dict[str, object]] = {}

    record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!a",
        to_id="!b",
        rx_time=100,
        portnum="NODEINFO_APP",
        hops=1,
        rx_snr=7.5,
        rx_rssi=-91,
        include_live_count=True,
    )
    record_direct_edge_observation(
        session_edges=session_edges,
        historical_edges=historical_edges,
        from_id="!a",
        to_id="!b",
        rx_time=110,
        portnum="NODEINFO_APP",
        hops=2,
        rx_snr=1.5,
        rx_rssi=-101,
        include_live_count=True,
    )

    edge = session_edges[("!a", "!b")]
    assert edge["snr_count"] == 2
    assert edge["snr_sum"] == 9.0
    assert edge["snr_min"] == 1.5
    assert edge["snr_max"] == 7.5
    assert edge["rssi_count"] == 2
    assert edge["rssi_sum"] == -192.0
    assert edge["rssi_min"] == -101.0
    assert edge["rssi_max"] == -91.0

    hist_edge = historical_edges[("!a", "!b")]
    assert hist_edge["snr_count"] == 2
    assert hist_edge["rssi_count"] == 2


def test_decode_connections_rows_and_snapshot_expose_link_signal_rollups() -> None:
    decoded_rows = decode_connections_rows(
        [
            (
                "!11111111",
                "!22222222",
                100,
                220,
                6,
                '["NODEINFO_APP","TEXT_MESSAGE_APP"]',
                1,
                7,
                6,
                18.0,
                3,
                2.0,
                9.0,
                -282.0,
                3,
                -104.0,
                -86.0,
            )
        ]
    )

    historical_edges = build_historical_edges(decoded_rows)
    edge_rows, real_edge_count = build_edge_snapshot_rows(
        session_edges={},
        historical_edges=historical_edges,
        nodes_by_id={},
        min_real_link_count=2,
        format_epoch_fn=lambda value: value,
    )

    assert real_edge_count == 1
    assert len(edge_rows) == 1
    row = edge_rows[0]
    assert row["avg_snr"] == 6.0
    assert row["snr_samples"] == 3
    assert row["snr_min"] == 2.0
    assert row["snr_max"] == 9.0
    assert row["avg_rssi"] == -94.0
    assert row["rssi_samples"] == 3
    assert row["rssi_min"] == -104.0
    assert row["rssi_max"] == -86.0


def test_snapshot_falls_back_to_live_signal_metrics_when_history_has_none() -> None:
    session_edges = {
        ("!aaaa0001", "!bbbb0002"): {
            "from": "!aaaa0001",
            "to": "!bbbb0002",
            "count": 2,
            "first_rx_time": 100,
            "last_rx_time": 160,
            "portnums": {"NODEINFO_APP"},
            "last_hops": 1,
            "hops_sum": 2,
            "hops_count": 2,
            "snr_sum": 12.0,
            "snr_count": 2,
            "snr_min": 4.0,
            "snr_max": 8.0,
            "rssi_sum": -186.0,
            "rssi_count": 2,
            "rssi_min": -95.0,
            "rssi_max": -91.0,
        }
    }
    historical_edges = {
        ("!aaaa0001", "!bbbb0002"): {
            "from": "!aaaa0001",
            "to": "!bbbb0002",
            "count": 9,
            "first_rx_time": 50,
            "last_rx_time": 90,
            "portnums": {"NODEINFO_APP"},
            "last_hops": 1,
            "hops_sum": 9,
            "hops_count": 9,
            "snr_sum": 0.0,
            "snr_count": 0,
            "snr_min": None,
            "snr_max": None,
            "rssi_sum": 0.0,
            "rssi_count": 0,
            "rssi_min": None,
            "rssi_max": None,
        }
    }

    edge_rows, real_edge_count = build_edge_snapshot_rows(
        session_edges=session_edges,
        historical_edges=historical_edges,
        nodes_by_id={},
        min_real_link_count=2,
        format_epoch_fn=lambda value: value,
    )

    assert real_edge_count == 1
    row = edge_rows[0]
    assert row["lifetime_count"] == 9
    assert row["session_count"] == 2
    assert row["avg_snr"] == 6.0
    assert row["avg_rssi"] == -93.0
    assert row["snr_samples"] == 2
    assert row["rssi_samples"] == 2
