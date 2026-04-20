import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.helpers import to_int
from meshdash.history_backfill import backfill_node_capabilities
from meshdash.history_capabilities import decode_node_capabilities_rows
from meshdash.history_queries import fetch_node_capability_rows
from meshdash.history_schema import initialize_history_schema
from meshdash.history_writes import save_packet_event_and_rollups


def test_save_packet_event_and_rollups_persists_latest_node_names_in_capabilities() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)

    summary = {
        "from": "!a038f788",
        "to": "!08b3cb6d",
        "portnum": "NODEINFO_APP",
        "rx_time_unix": 1776514783,
        "hops": 2,
    }
    packet = {
        "fromId": "!a038f788",
        "toId": "!08b3cb6d",
        "rxTime": 1776514783,
        "decoded": {
            "portnum": "NODEINFO_APP",
            "user": {
                "id": "!a038f788",
                "longName": "NOT A HACKER",
                "shortName": "NAH",
            },
        },
    }

    save_packet_event_and_rollups(conn, summary, packet=packet, now_unix_fn=lambda: 1776514784.0)

    rows = fetch_node_capability_rows(conn)
    decoded = decode_node_capabilities_rows(rows)
    assert decoded["!a038f788"]["last_long_name"] == "NOT A HACKER"
    assert decoded["!a038f788"]["last_short_name"] == "NAH"
    assert decoded["!a038f788"]["names_updated_unix"] == 1776514783


def test_backfill_node_capabilities_recovers_names_for_existing_history() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)

    conn.execute(
        """
        INSERT INTO node_capabilities(
          node_id, last_seen_unix, has_position, last_position_unix,
          last_hops, battery_level, battery_updated_unix
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        ("!a038f788", 1776514000, 0, None, 2, None, None),
    )

    summary = {
        "captured_at": "2026-04-18 12:19:44Z",
        "from": "!a038f788",
        "to": "!08b3cb6d",
        "portnum": "NODEINFO_APP",
        "rx_time_unix": 1776514783,
    }
    packet = {
        "fromId": "!a038f788",
        "toId": "!08b3cb6d",
        "decoded": {
            "portnum": "NODEINFO_APP",
            "user": {
                "id": "!a038f788",
                "longName": "NOT A HACKER",
                "shortName": "NAH",
            },
        },
    }
    conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        (1776514784, json.dumps(summary, separators=(",", ":")), json.dumps(packet, separators=(",", ":"))),
    )
    conn.commit()

    backfill_node_capabilities(conn, to_int_fn=to_int)

    rows = fetch_node_capability_rows(conn)
    decoded = decode_node_capabilities_rows(rows)
    assert decoded["!a038f788"]["last_long_name"] == "NOT A HACKER"
    assert decoded["!a038f788"]["last_short_name"] == "NAH"
    assert decoded["!a038f788"]["names_updated_unix"] == 1776514784
