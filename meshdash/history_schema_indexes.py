INDEX_SCHEMA_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_packets_created_unix ON packets(created_unix)",
    "CREATE INDEX IF NOT EXISTS idx_chat_created_unix ON chat(created_unix)",
    "CREATE INDEX IF NOT EXISTS idx_connections_last_seen_unix ON connections(last_seen_unix)",
    "CREATE INDEX IF NOT EXISTS idx_packet_events_created_unix ON packet_events(created_unix)",
    "CREATE INDEX IF NOT EXISTS idx_packet_events_from_id ON packet_events(from_id)",
    "CREATE INDEX IF NOT EXISTS idx_packet_events_to_id ON packet_events(to_id)",
    "CREATE INDEX IF NOT EXISTS idx_packet_events_portnum ON packet_events(portnum)",
    "CREATE INDEX IF NOT EXISTS idx_node_positions_created_unix ON node_positions(created_unix)",
    "CREATE INDEX IF NOT EXISTS idx_node_positions_node_id_created_unix ON node_positions(node_id, created_unix)",
    "CREATE INDEX IF NOT EXISTS idx_node_capabilities_last_seen_unix ON node_capabilities(last_seen_unix)",
    # Optimize node history lookups (/api/history/node), which filter by node_id
    # and bucket range then order by bucket_unix.
    "CREATE INDEX IF NOT EXISTS idx_node_metrics_1m_node_id_bucket_unix ON node_metrics_1m(node_id, bucket_unix)",
    "CREATE INDEX IF NOT EXISTS idx_node_metrics_1m_last_seen_unix ON node_metrics_1m(last_seen_unix)",
    "CREATE INDEX IF NOT EXISTS idx_link_metrics_1m_last_seen_unix ON link_metrics_1m(last_seen_unix)",
    "CREATE INDEX IF NOT EXISTS idx_summary_metrics_1m_last_seen_unix ON summary_metrics_1m(last_seen_unix)",
    "CREATE INDEX IF NOT EXISTS idx_environment_metrics_1m_last_seen_unix ON environment_metrics_1m(last_seen_unix)",
    "CREATE INDEX IF NOT EXISTS idx_environment_metrics_1m_metric_key_bucket_unix ON environment_metrics_1m(metric_key, bucket_unix)",
    "CREATE INDEX IF NOT EXISTS idx_environment_metrics_1m_node_id_bucket_unix ON environment_metrics_1m(node_id, bucket_unix)",
]
