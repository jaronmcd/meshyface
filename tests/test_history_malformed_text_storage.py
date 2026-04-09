import sqlite3
import sys
import threading
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.history_store_malformed_text import load_malformed_text_history
from meshdash.history_prune import prune_history_tables
from meshdash.history_raw_writes import save_packet_record
from meshdash.history_schema import initialize_history_schema


def test_save_packet_record_persists_malformed_text_payloads() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)

    save_packet_record(
        conn,
        {
            "summary": {
                "from": "!aca96ba8",
                "from_long_name": "Weird Sender",
                "portnum": "TEXT_MESSAGE_APP",
                "packet_id": 7394,
                "rx_time_unix": 1775759976,
                "decoded_text": None,
                "is_reaction": False,
            },
            "packet": {
                "id": 7394,
                "fromId": "!aca96ba8",
                "decoded": {
                    "portnum": "TEXT_MESSAGE_APP",
                    "payload": "fe9ef9f2dbf9ffffe2fe80cbef",
                },
            },
        },
        now_unix_fn=lambda: 1775759973,
    )

    row = conn.execute(
        """
        SELECT packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text
        FROM malformed_text_payloads
        """
    ).fetchone()

    assert row is not None
    assert int(row[0]) == 1
    assert row[1] == "!aca96ba8"
    assert row[2] == "Weird Sender"
    assert row[3] == "TEXT_MESSAGE_APP"
    assert int(row[4]) == 7394
    assert int(row[5]) == 1775759976
    assert row[6] == "fe9ef9f2dbf9ffffe2fe80cbef"


def test_save_packet_record_skips_normal_text_messages() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)

    save_packet_record(
        conn,
        {
            "summary": {
                "from": "!aca96ba8",
                "portnum": "TEXT_MESSAGE_APP",
                "packet_id": 7401,
                "rx_time_unix": 1775760001,
                "decoded_text": "hello",
                "is_reaction": False,
            },
            "packet": {
                "id": 7401,
                "fromId": "!aca96ba8",
                "decoded": {
                    "portnum": "TEXT_MESSAGE_APP",
                    "text": "hello",
                    "payload": "68656c6c6f",
                },
            },
        },
        now_unix_fn=lambda: 1775760001,
    )

    row = conn.execute("SELECT COUNT(*) FROM malformed_text_payloads").fetchone()
    assert row is not None
    assert int(row[0]) == 0


def test_prune_history_tables_prunes_malformed_text_payloads() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    conn.execute(
        """
        INSERT INTO malformed_text_payloads(
          created_unix, packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (100, 1, "!oldnode1", "Old Node", "TEXT_MESSAGE_APP", 1, 100, "ff"),
    )
    conn.execute(
        """
        INSERT INTO malformed_text_payloads(
          created_unix, packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (200, 2, "!newnode2", "New Node", "TEXT_MESSAGE_APP", 2, 200, "fe"),
    )

    prune_history_tables(
        conn,
        now_unix=250,
        retention_seconds=0,
        event_retention_seconds=75,
        rollup_retention_seconds=0,
        max_rows=0,
        event_max_rows=0,
    )

    rows = conn.execute(
        "SELECT from_id, payload_text FROM malformed_text_payloads ORDER BY id ASC"
    ).fetchall()
    assert rows == [("!newnode2", "fe")]


def test_load_malformed_text_history_groups_senders_and_filters_node() -> None:
    conn = sqlite3.connect(":memory:")
    initialize_history_schema(conn)
    conn.executemany(
        """
        INSERT INTO malformed_text_payloads(
          created_unix, packet_row_id, from_id, from_label, portnum, packet_id, rx_time_unix, payload_text
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (900, 1, "!aca96ba8", "Weird Sender", "TEXT_MESSAGE_APP", 101, 910, "e98ffe07"),
            (920, 2, "!aca96ba8", "Weird Sender", "TEXT_MESSAGE_APP", 102, 930, "fe9ef9f2dbf9ffff"),
            (940, 3, "!bbbb0001", "Another Sender", "TEXT_MESSAGE_APP", 103, 950, "ccdd0011"),
        ],
    )

    class DummyStore:
        def __init__(self, db_conn: sqlite3.Connection) -> None:
            self._conn = db_conn
            self._read_conn = None
            self._lock = threading.Lock()

    store = DummyStore(conn)

    with patch("meshdash.history_store_malformed_text.time.time", return_value=1000):
        payload = load_malformed_text_history(store, window_hours=1, limit=2)

    assert payload["ok"] is True
    assert payload["summary"]["total_packets"] == 3
    assert payload["summary"]["distinct_senders"] == 2
    assert len(payload["senders"]) == 2
    assert payload["senders"][0]["from_id"] == "!aca96ba8"
    assert payload["senders"][0]["count"] == 2
    assert payload["senders"][0]["last_payload_preview"] == "fe9ef9f2dbf9ffff"
    assert len(payload["entries"]) == 2
    assert payload["entries"][0]["from_id"] == "!bbbb0001"

    with patch("meshdash.history_store_malformed_text.time.time", return_value=1000):
        filtered = load_malformed_text_history(store, window_hours=1, limit=10, node_id="!aca96ba8")

    assert filtered["summary"]["total_packets"] == 2
    assert filtered["summary"]["distinct_senders"] == 1
    assert all(entry["from_id"] == "!aca96ba8" for entry in filtered["entries"])
