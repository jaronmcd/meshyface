import sqlite3

from meshdash.history_raw_writes import save_chat_record, save_packet_record
from meshdash.history.db import initialize_history_schema


def test_save_packet_record_inserts_packet_and_calls_rollup_writer():
    conn = sqlite3.connect(":memory:")
    called: dict[str, object] = {}
    try:
        initialize_history_schema(conn)

        def _rollup_stub(inner_conn, summary, *, packet, now_unix_fn):
            called["conn"] = inner_conn
            called["summary"] = summary
            called["packet"] = packet
            called["now"] = int(now_unix_fn())

        save_packet_record(
            conn,
            {"summary": {"from": "!a", "rx_time_unix": 50}, "packet": {"raw": 1}},
            now_unix_fn=lambda: 123,
            save_packet_event_and_rollups_fn=_rollup_stub,
        )

        row = conn.execute(
            "SELECT created_unix, summary_json, packet_json FROM packets"
        ).fetchone()
        assert row == (123, '{"from":"!a","rx_time_unix":50}', '{"raw":1}')
        assert called["conn"] is conn
        assert called["summary"] == {"from": "!a", "rx_time_unix": 50}
        assert called["packet"] == {"raw": 1}
        assert called["now"] == 123
    finally:
        conn.close()


def test_save_packet_record_skips_rollup_for_non_dict_summary():
    conn = sqlite3.connect(":memory:")
    called = False
    try:
        initialize_history_schema(conn)

        def _rollup_stub(*_args, **_kwargs):
            nonlocal called
            called = True

        save_packet_record(
            conn,
            {"summary": "n/a", "packet": {"raw": 1}},
            now_unix_fn=lambda: 200,
            save_packet_event_and_rollups_fn=_rollup_stub,
        )

        assert conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 1
        assert called is False
    finally:
        conn.close()


def test_save_chat_record_inserts_chat_row():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        save_chat_record(conn, {"text": "hello", "from": "!a"}, now_unix_fn=lambda: 250)
        row = conn.execute("SELECT created_unix, message_json FROM chat").fetchone()
        assert row == (250, '{"text":"hello","from":"!a"}')
    finally:
        conn.close()
