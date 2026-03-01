import sqlite3

from meshdash.history_schema import initialize_history_schema


def test_initialize_history_schema_creates_core_tables_and_indexes():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        index_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }

        assert "packets" in table_names
        assert "chat" in table_names
        assert "connections" in table_names
        assert "packet_events" in table_names
        assert "node_positions" in table_names
        assert "node_capabilities" in table_names
        assert "node_metrics_1m" in table_names
        assert "link_metrics_1m" in table_names
        assert "summary_metrics_1m" in table_names

        assert "idx_packets_created_unix" in index_names
        assert "idx_chat_created_unix" in index_names
        assert "idx_connections_last_seen_unix" in index_names
        assert "idx_node_metrics_1m_last_seen_unix" in index_names
        assert "idx_summary_metrics_1m_last_seen_unix" in index_names
    finally:
        conn.close()
