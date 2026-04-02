import sqlite3

from meshdash.history_prune import prune_history_tables
from meshdash.history.db import initialize_history_schema


def test_prune_history_tables_applies_retention_and_row_limits():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)

        # Packets/chat: 3 rows each (old, mid, newest)
        conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, '{}', '{}')", (10,))
        conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, '{}', '{}')", (95,))
        conn.execute("INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, '{}', '{}')", (99,))
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(?, '{}')", (10,))
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(?, '{}')", (95,))
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(?, '{}')", (99,))

        # Connections with different last_seen_unix
        conn.execute(
            "INSERT INTO connections(from_id, to_id, first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count) VALUES('!a','!b',10,10,1,'[]',1,1,1)"
        )
        conn.execute(
            "INSERT INTO connections(from_id, to_id, first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count) VALUES('!c','!d',95,95,1,'[]',1,1,1)"
        )
        conn.execute(
            "INSERT INTO connections(from_id, to_id, first_seen_unix, last_seen_unix, seen_count, portnums_json, last_hops, hops_sum, hops_count) VALUES('!e','!f',99,99,1,'[]',1,1,1)"
        )

        # Event tables + capabilities
        conn.execute("INSERT INTO packet_events(created_unix, summary_json) VALUES(10, '{}')")
        conn.execute("INSERT INTO packet_events(created_unix, summary_json) VALUES(95, '{}')")
        conn.execute("INSERT INTO packet_events(created_unix, summary_json) VALUES(99, '{}')")
        conn.execute("INSERT INTO node_positions(created_unix, node_id, lat, lon) VALUES(10, '!a', 44.0, -93.0)")
        conn.execute("INSERT INTO node_positions(created_unix, node_id, lat, lon) VALUES(95, '!a', 44.1, -93.1)")
        conn.execute("INSERT INTO node_positions(created_unix, node_id, lat, lon) VALUES(99, '!a', 44.2, -93.2)")
        conn.execute(
            "INSERT INTO node_capabilities(node_id, last_seen_unix, has_position, last_position_unix, last_hops, battery_level, battery_updated_unix) VALUES('!old', 10, 0, NULL, NULL, NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO node_capabilities(node_id, last_seen_unix, has_position, last_position_unix, last_hops, battery_level, battery_updated_unix) VALUES('!new', 99, 1, 99, 2, 80, 99)"
        )

        # Rollup tables
        conn.execute(
            "INSERT INTO node_metrics_1m(bucket_unix, node_id, packet_count, snr_sum, snr_count, rssi_sum, rssi_count, hops_sum, hops_count, last_seen_unix) VALUES(10, '!a', 1, 0.0, 0, 0.0, 0, 0, 0, 10)"
        )
        conn.execute(
            "INSERT INTO node_metrics_1m(bucket_unix, node_id, packet_count, snr_sum, snr_count, rssi_sum, rssi_count, hops_sum, hops_count, last_seen_unix) VALUES(99, '!a', 1, 0.0, 0, 0.0, 0, 0, 0, 99)"
        )
        conn.execute(
            "INSERT INTO link_metrics_1m(bucket_unix, from_id, to_id, packet_count, snr_sum, snr_count, rssi_sum, rssi_count, hops_sum, hops_count, last_seen_unix) VALUES(10, '!a', '!b', 1, 0.0, 0, 0.0, 0, 0, 0, 10)"
        )
        conn.execute(
            "INSERT INTO link_metrics_1m(bucket_unix, from_id, to_id, packet_count, snr_sum, snr_count, rssi_sum, rssi_count, hops_sum, hops_count, last_seen_unix) VALUES(99, '!a', '!b', 1, 0.0, 0, 0.0, 0, 0, 0, 99)"
        )
        conn.execute(
            "INSERT INTO summary_metrics_1m(bucket_unix, node_count, nodes_with_position, live_packet_count, real_edge_count, last_seen_unix) VALUES(0, 1, 1, 1, 1, 10)"
        )
        conn.execute(
            "INSERT INTO summary_metrics_1m(bucket_unix, node_count, nodes_with_position, live_packet_count, real_edge_count, last_seen_unix) VALUES(60, 2, 2, 2, 2, 99)"
        )
        conn.execute(
            """
            INSERT INTO environment_metrics_1m(
              bucket_unix, node_id, node_label, metric_key, metric_label,
              sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
            ) VALUES(0, '!a', 'alpha', 'temperature', 'Temperature',
                     1, 21.5, 21.5, 21.5, 21.5, 10)
            """
        )
        conn.execute(
            """
            INSERT INTO environment_metrics_1m(
              bucket_unix, node_id, node_label, metric_key, metric_label,
              sample_count, value_sum, value_min, value_max, last_value, last_seen_unix
            ) VALUES(60, '!a', 'alpha', 'temperature', 'Temperature',
                     2, 43.0, 21.0, 22.0, 22.0, 99)
            """
        )
        conn.commit()

        prune_history_tables(
            conn,
            now_unix=100,
            retention_seconds=10,
            event_retention_seconds=10,
            rollup_retention_seconds=10,
            max_rows=2,
            event_max_rows=2,
        )
        conn.commit()

        assert conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM connections").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM packet_events").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM node_positions").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM node_capabilities").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM node_metrics_1m").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM link_metrics_1m").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM summary_metrics_1m").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM environment_metrics_1m").fetchone()[0] == 1
    finally:
        conn.close()
