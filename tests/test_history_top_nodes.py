import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_schema import initialize_history_schema
from meshdash.history_store_nodes import load_node_position_counts
from meshdash.history_top_nodes import load_top_nodes
from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_sections import build_html_shell


def _make_store(conn: sqlite3.Connection) -> SimpleNamespace:
    return SimpleNamespace(
        _conn=conn,
        _read_conn=None,
        _read_lock=None,
        _lock=threading.Lock(),
    )


def test_top_nodes_saved_packets_and_chat_categories_use_history_rollups() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    conn.executemany(
        """
        INSERT INTO node_saved_counts(node_id, saved_packets, saved_points, saved_last_seen_unix)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("!11111111", 12, 5, 1000),
            ("!22222222", 30, 9, 1100),
            ("^all", 99, 99, 1200),
        ],
    )
    conn.executemany(
        """
        INSERT INTO packet_events(created_unix, from_id, to_id, portnum)
        VALUES (?, ?, ?, ?)
        """,
        [
            (100, "!11111111", "^all", "TEXT_MESSAGE_APP"),
            (101, "!11111111", "!22222222", "TEXT_MESSAGE_APP"),
            (102, "!22222222", "^all", "TELEMETRY_APP"),
        ],
    )
    conn.commit()

    saved = load_top_nodes(store, category="saved_packets", limit=10)
    assert [item["node_id"] for item in saved["items"]] == ["!22222222", "!11111111"]
    assert saved["items"][0]["value"] == 30
    assert saved["items"][0]["secondary_value"] == 9

    chats = load_top_nodes(store, category="chats", limit=10)
    assert chats["category"] == "chat_packets"
    assert chats["items"] == [
        {
            "rank": 1,
            "node_id": "!11111111",
            "value": 2,
            "secondary_value": 2,
            "last_seen_unix": 101,
            "last_seen": chats["items"][0]["last_seen"],
        }
    ]


def test_top_nodes_all_category_returns_grouped_ranked_lists() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    conn.executemany(
        """
        INSERT INTO node_saved_counts(node_id, saved_packets, saved_points, saved_last_seen_unix)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("!11111111", 12, 5, 1000),
            ("!22222222", 30, 9, 1100),
        ],
    )
    conn.executemany(
        """
        INSERT INTO packet_events(created_unix, from_id, to_id, portnum)
        VALUES (?, ?, ?, ?)
        """,
        [
            (100, "!11111111", "^all", "TEXT_MESSAGE_APP"),
            (101, "!11111111", "!22222222", "TEXT_MESSAGE_APP"),
            (102, "!22222222", "^all", "TELEMETRY_APP"),
        ],
    )
    conn.commit()

    payload = load_top_nodes(store, category="all", limit=10)
    assert payload["category"] == "all"
    assert payload["category_label"] == "All Categories"
    assert payload["categories"][0]["id"] == "all"

    groups = {group["category"]: group for group in payload["groups"]}
    assert groups["saved_packets"]["items"][0]["node_id"] == "!22222222"
    assert groups["saved_packets"]["items"][0]["value"] == 30
    assert groups["chat_packets"]["items"][0]["node_id"] == "!11111111"
    assert groups["chat_packets"]["items"][0]["value"] == 2
    assert payload["item_count"] >= 3


def test_top_nodes_can_exclude_local_node_from_rankings() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    conn.executemany(
        """
        INSERT INTO node_saved_counts(node_id, saved_packets, saved_points, saved_last_seen_unix)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("!self0001", 1000, 20, 1200),
            ("!11111111", 12, 5, 1000),
            ("!22222222", 30, 9, 1100),
        ],
    )
    conn.commit()

    payload = load_top_nodes(
        store,
        category="saved_packets",
        limit=2,
        exclude_node_ids=["!SELF0001"],
    )

    assert [item["node_id"] for item in payload["items"]] == ["!22222222", "!11111111"]
    assert [item["rank"] for item in payload["items"]] == [1, 2]


def test_top_nodes_links_count_unique_peers_and_link_packets() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    conn.executemany(
        """
        INSERT INTO connections(
          from_id, to_id, first_seen_unix, last_seen_unix, seen_count, portnums_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("!11111111", "!22222222", 100, 200, 7, "[]"),
            ("!33333333", "!11111111", 110, 230, 4, "[]"),
            ("!22222222", "!33333333", 120, 240, 3, "[]"),
        ],
    )
    conn.commit()

    links = load_top_nodes(store, category="links", limit=10)
    rows_by_id = {item["node_id"]: item for item in links["items"]}
    assert rows_by_id["!11111111"]["value"] == 2
    assert rows_by_id["!11111111"]["secondary_value"] == 11

    link_packets = load_top_nodes(store, category="link_packets", limit=10)
    assert link_packets["items"][0]["node_id"] == "!11111111"
    assert link_packets["items"][0]["value"] == 11
    assert link_packets["items"][0]["secondary_value"] == 2


def test_node_position_counts_follow_position_inserts_and_deletes() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    store = _make_store(conn)

    conn.executemany(
        """
        INSERT INTO node_positions(created_unix, node_id, lat, lon)
        VALUES (?, ?, ?, ?)
        """,
        [
            (100, "!11111111", 44.9, -93.1),
            (200, "!11111111", 45.0, -93.2),
            (150, "!22222222", 46.0, -94.0),
        ],
    )
    conn.commit()

    counts = load_node_position_counts(store)
    assert counts["!11111111"]["position_points"] == 2
    assert counts["!11111111"]["position_last_seen_unix"] == 200
    assert counts["!22222222"]["position_points"] == 1

    conn.execute(
        "DELETE FROM node_positions WHERE node_id = ? AND created_unix = ?",
        ("!11111111", 200),
    )
    conn.commit()

    counts = load_node_position_counts(store)
    assert counts["!11111111"]["position_points"] == 1
    assert counts["!11111111"]["position_last_seen_unix"] == 100


def test_dashboard_adds_network_top10_subview() -> None:
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

    assert 'data-network-subview="top10"' in html
    assert 'id="network-map-panel-top10"' in html
    assert 'id="network-top-nodes-primary-controls"' in html
    assert 'id="network-top-nodes-category"' in html


def test_dashboard_js_wires_network_top_nodes_fetch_and_render() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const networkTopNodesCategoryStorageKey = "meshDashboardNetworkTopNodesCategoryV1";' in js
    assert 'let networkTopNodesCategory = "all";' in js
    assert 'let nodeCityHintCache = new Map();' in js
    assert '{ id: "all", label: "All Categories", unit: "" }' in js
    assert 'function normalizeNetworkTopNodesCategory(raw) {' in js
    assert 'function networkTopNodesExcludedLocalIds(state = latestState) {' in js
    assert 'items: networkTopNodesItemsFromMap(counts, 10, excludedNodeIds)' in js
    assert 'function networkTopNodesNodeLocation(nodeId, state = latestState, item = null) {' in js
    assert 'function hydrateNetworkTopNodeCities(root) {' in js
    assert 'function networkTopNodesPayloadHasItems(payload) {' in js
    assert 'function networkTopNodesVisualEmoji(nodeId, state = latestState) {' in js
    assert 'function networkTopNodesRowsHtml(items, payload, state = latestState) {' in js
    assert 'class="network-top-node-city${citySource === "estimated" ? " is-estimated" : ""}"' in js
    assert 'const nodeEmojiClass = nodeEmoji ? ` has-node-emoji${nodeWatermarkTextClass}` : "";' in js
    assert 'class="network-top-node-row${nodeEmojiClass}"' in js
    assert 'data-node-emoji="${escAttr(nodeEmoji)}"' in js
    assert 'class="network-top-nodes-group"' in js
    assert 'const displayGroups = groups.length > 0' in js
    assert 'function networkTopNodesGroupHtml(group, state = latestState, options = {}) {' in js
    assert 'const showGroupHeaders = category === "all" || displayGroups.length > 1;' in js
    assert 'networkTopNodesGroupHtml(group, state, { showHeader: showGroupHeaders })' in js
    assert 'hydrateNetworkTopNodeCities(list);' in js
    assert 'function renderNetworkTopNodes(state = latestState, options = {}) {' in js
    assert 'function syncNetworkTopNodesPrimaryControls(viewName = activeLayoutView, subviewName = activeNetworkSubview)' in js
    assert 'const controlsHost = document.getElementById("network-top-nodes-primary-controls");' in js
    assert "/api/history/top_nodes?category=" in js
    assert 'if (renderSubview && normalizedView === "network" && next === "top10") {' in js


def test_dashboard_css_keeps_top_node_bar_below_row_text() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".network-top-node-bar" in css
    assert ".network-top-node-city" in css
    assert ".network-top-node-city[hidden]" in css
    assert ".network-top-node-row.has-node-emoji::after" in css
    assert '[data-theme="dark"] .network-top-node-row.has-node-emoji::after' in css
    watermark_idx = css.index(".network-top-node-row.has-node-emoji::after")
    content_idx = css.index(".network-top-node-rank,", watermark_idx)
    watermark_css = css[watermark_idx:content_idx]
    assert "left: 0;" in watermark_css
    assert "width: 52px;" in watermark_css
    assert "text-align: center;" in watermark_css
    assert "position: relative;" in css
    assert "display: block;" in css
    assert "width: 100%;" in css
    assert "min-height: 4px;" in css
    assert "margin-top: 7px;" in css


def test_dashboard_js_places_top_node_bar_inside_text_column() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    bar_idx = js.index('class="network-top-node-bar"')
    value_idx = js.index('class="network-top-node-value"', bar_idx)
    main_close_idx = js.rindex("</span>", 0, value_idx)
    assert bar_idx < main_close_idx < value_idx
