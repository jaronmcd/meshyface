import sqlite3

from meshdash.history_queries import (
    fetch_connection_rows,
    fetch_node_capability_rows,
    fetch_node_history_rows,
    fetch_packet_search_rows,
    fetch_node_saved_count_rows,
    fetch_online_activity_rows,
    fetch_summary_metrics_rows,
    fetch_recent_chat_rows,
    fetch_recent_packet_rows,
)
from meshdash.history.db import initialize_history_schema


def _insert_metric(conn, bucket_unix, node_id, packet_count, last_seen_unix):
    conn.execute(
        """
        INSERT INTO node_metrics_1m(
          bucket_unix, node_id, packet_count,
          snr_sum, snr_count, snr_min, snr_max,
          rssi_sum, rssi_count, rssi_min, rssi_max,
          hops_sum, hops_count, hops_min, hops_max,
          last_seen_unix
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bucket_unix,
            node_id,
            packet_count,
            1.0,
            1,
            1.0,
            1.0,
            -100.0,
            1,
            -100.0,
            -100.0,
            2,
            1,
            2,
            2,
            last_seen_unix,
        ),
    )


def test_fetch_recent_packet_and_chat_rows_apply_limit_and_newest_order():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(1, '{\"a\":1}', '{\"p\":1}')"
        )
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(2, '{\"a\":2}', '{\"p\":2}')"
        )
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(3, '{\"a\":3}', '{\"p\":3}')"
        )
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(1, '{\"m\":1}')")
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(2, '{\"m\":2}')")

        packet_rows = fetch_recent_packet_rows(conn, limit=2)
        chat_rows = fetch_recent_chat_rows(conn, limit=1)

        assert packet_rows == [('{"a":3}', '{"p":3}'), ('{"a":2}', '{"p":2}')]
        assert chat_rows == [('{"m":2}',)]
    finally:
        conn.close()


def test_fetch_packet_search_rows_returns_chronological_rows_with_optional_limit():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(1, '{\"k\":\"a\"}', '{\"p\":1}')"
        )
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(2, '{\"k\":\"b\"}', '{\"p\":2}')"
        )
        conn.execute(
            "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(3, '{\"k\":\"c\"}', '{\"p\":3}')"
        )

        all_rows = fetch_packet_search_rows(conn, limit=0)
        limited_rows = fetch_packet_search_rows(conn, limit=2)

        assert [row[2] for row in all_rows] == [
            '{"k":"a"}',
            '{"k":"b"}',
            '{"k":"c"}',
        ]
        assert [row[2] for row in limited_rows] == [
            '{"k":"b"}',
            '{"k":"c"}',
        ]
    finally:
        conn.close()


def test_fetch_recent_chat_rows_excludes_file_transfer_protocol_messages_before_limit():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute("INSERT INTO chat(created_unix, message_json) VALUES(1, '{\"text\":\"real-old\"}')")
        conn.execute(
            "INSERT INTO chat(created_unix, message_json) VALUES(2, '{\"text\":\"MF_FILE_V1|A|mtest123|0|4|AA==\"}')"
        )
        rows = fetch_recent_chat_rows(conn, limit=1)
        assert rows == [('{"text":"real-old"}',)]
    finally:
        conn.close()


def test_fetch_history_and_aggregate_rows_from_metrics_tables():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        _insert_metric(conn, 60, "!a", 2, 80)
        _insert_metric(conn, 120, "!a", 3, 140)
        _insert_metric(conn, 120, "!b", 1, 130)
        conn.execute(
            "INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view) VALUES(125, '!a', 44.95, -93.1, 301.0, 8)"
        )
        conn.execute(
            "INSERT INTO node_positions(created_unix, node_id, lat, lon, altitude, sats_in_view) VALUES(65, '!a', 44.94, -93.2, 300.0, 7)"
        )
        conn.execute(
            "INSERT INTO node_capabilities(node_id, last_seen_unix, has_position, last_position_unix, last_hops, battery_level, battery_updated_unix) VALUES('!a', 140, 1, 125, 2, 85, 140)"
        )
        conn.execute(
            "INSERT INTO node_capabilities(node_id, last_seen_unix, has_position, last_position_unix, last_hops, battery_level, battery_updated_unix) VALUES('!b', 130, 0, NULL, NULL, NULL, NULL)"
        )
        conn.execute(
            """
            INSERT INTO packets(created_unix, summary_json, packet_json)
            VALUES(135, '{"from":"!a","to":"^all","rx_time_unix":135,"portnum":"NODEINFO_APP"}',
                        '{"fromId":"!a","toId":"^all","rxTime":135,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!a","shortName":"Alpha","longName":"Alpha One"}}}')
            """
        )
        conn.execute(
            """
            INSERT INTO packets(created_unix, summary_json, packet_json)
            VALUES(40, '{"from":"!a","to":"^all","rx_time_unix":40,"portnum":"NODEINFO_APP"}',
                       '{"fromId":"!a","toId":"^all","rxTime":40,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!a","shortName":"Old","longName":"Old Alpha"}}}')
            """
        )

        metric_rows, position_rows, packet_rows = fetch_node_history_rows(
            conn, node_id="!a", cutoff=70, limit=10
        )
        hour_rows, distinct_nodes = fetch_online_activity_rows(conn, cutoff=0)
        saved_rows = fetch_node_saved_count_rows(conn)
        capability_rows = fetch_node_capability_rows(conn)

        assert [r[0] for r in metric_rows] == [120]
        assert [r[0] for r in position_rows] == [125]
        assert len(packet_rows) == 1
        assert packet_rows[0][0] == 135
        assert hour_rows == [(0, 2)]
        assert distinct_nodes == 2
        assert sorted((r[0], r[1], r[2]) for r in saved_rows) == [
            ("!a", 5, 2),
            ("!b", 1, 1),
        ]
        assert [r[0] for r in capability_rows] == ["!a", "!b"]
    finally:
        conn.close()


def test_fetch_connection_rows_orders_by_last_seen_desc():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO connections(
              from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
              portnums_json, last_hops, hops_sum, hops_count
            ) VALUES('!a', '!b', 10, 100, 1, '[]', 1, 1, 1)
            """
        )
        conn.execute(
            """
            INSERT INTO connections(
              from_id, to_id, first_seen_unix, last_seen_unix, seen_count,
              portnums_json, last_hops, hops_sum, hops_count
            ) VALUES('!c', '!d', 20, 200, 2, '[]', 2, 3, 2)
            """
        )
        rows = fetch_connection_rows(conn)
        assert [r[0] for r in rows] == ["!c", "!a"]
    finally:
        conn.close()


def test_fetch_summary_metrics_rows_filters_and_orders_by_bucket():
    conn = sqlite3.connect(":memory:")
    try:
        initialize_history_schema(conn)
        conn.execute(
            """
            INSERT INTO summary_metrics_1m(
              bucket_unix, node_count, saved_node_count, online_node_count, nodes_with_position,
              live_packet_count, real_edge_count, last_seen_unix
            ) VALUES(60, 10, 6, 4, 8, 25, 4, 61)
            """
        )
        conn.execute(
            """
            INSERT INTO summary_metrics_1m(
              bucket_unix, node_count, saved_node_count, online_node_count, nodes_with_position,
              live_packet_count, real_edge_count, last_seen_unix
            ) VALUES(120, 12, 7, 5, 9, 30, 5, 121)
            """
        )
        rows = fetch_summary_metrics_rows(conn, cutoff=90, limit=10)
        assert rows == [
            (120, 12, 7, 5, 9, 30, 5),
        ]
    finally:
        conn.close()
