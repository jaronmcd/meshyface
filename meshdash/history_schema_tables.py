TABLE_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS packets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_unix INTEGER NOT NULL,
      summary_json TEXT NOT NULL,
      packet_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_unix INTEGER NOT NULL,
      message_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS connections (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      from_id TEXT NOT NULL,
      to_id TEXT NOT NULL,
      first_seen_unix INTEGER NOT NULL,
      last_seen_unix INTEGER NOT NULL,
      seen_count INTEGER NOT NULL,
      portnums_json TEXT NOT NULL,
      last_hops INTEGER,
      hops_sum INTEGER NOT NULL DEFAULT 0,
      hops_count INTEGER NOT NULL DEFAULT 0,
      UNIQUE(from_id, to_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS packet_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_unix INTEGER NOT NULL,
      from_id TEXT,
      to_id TEXT,
      portnum TEXT,
      rx_snr REAL,
      rx_rssi REAL,
      hops INTEGER,
      hop_start INTEGER,
      hop_limit INTEGER,
      channel TEXT,
      want_ack INTEGER,
      priority TEXT,
      summary_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS node_positions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_unix INTEGER NOT NULL,
      node_id TEXT NOT NULL,
      lat REAL NOT NULL,
      lon REAL NOT NULL,
      altitude REAL,
      sats_in_view INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS node_capabilities (
      node_id TEXT PRIMARY KEY,
      last_seen_unix INTEGER NOT NULL,
      has_position INTEGER NOT NULL DEFAULT 0,
      last_position_unix INTEGER,
      last_hops INTEGER,
      battery_level INTEGER,
      battery_updated_unix INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS node_metrics_1m (
      bucket_unix INTEGER NOT NULL,
      node_id TEXT NOT NULL,
      packet_count INTEGER NOT NULL,
      snr_sum REAL NOT NULL,
      snr_count INTEGER NOT NULL,
      snr_min REAL,
      snr_max REAL,
      rssi_sum REAL NOT NULL,
      rssi_count INTEGER NOT NULL,
      rssi_min REAL,
      rssi_max REAL,
      hops_sum INTEGER NOT NULL,
      hops_count INTEGER NOT NULL,
      hops_min INTEGER,
      hops_max INTEGER,
      last_seen_unix INTEGER NOT NULL,
      PRIMARY KEY(bucket_unix, node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS link_metrics_1m (
      bucket_unix INTEGER NOT NULL,
      from_id TEXT NOT NULL,
      to_id TEXT NOT NULL,
      packet_count INTEGER NOT NULL,
      snr_sum REAL NOT NULL,
      snr_count INTEGER NOT NULL,
      snr_min REAL,
      snr_max REAL,
      rssi_sum REAL NOT NULL,
      rssi_count INTEGER NOT NULL,
      rssi_min REAL,
      rssi_max REAL,
      hops_sum INTEGER NOT NULL,
      hops_count INTEGER NOT NULL,
      hops_min INTEGER,
      hops_max INTEGER,
      last_seen_unix INTEGER NOT NULL,
      PRIMARY KEY(bucket_unix, from_id, to_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS summary_metrics_1m (
      bucket_unix INTEGER PRIMARY KEY,
      node_count INTEGER NOT NULL DEFAULT 0,
      nodes_with_position INTEGER NOT NULL DEFAULT 0,
      live_packet_count INTEGER NOT NULL DEFAULT 0,
      real_edge_count INTEGER NOT NULL DEFAULT 0,
      last_seen_unix INTEGER NOT NULL
    )
    """,

    # Fast per-node rollup of history storage totals.
    #
    # This is maintained via triggers on node_metrics_1m so that the dashboard
    # UI (which polls /api/state frequently) does *not* need to GROUP BY over
    # the entire metrics table on every refresh.
    """
    CREATE TABLE IF NOT EXISTS node_saved_counts (
      node_id TEXT PRIMARY KEY,
      saved_packets INTEGER NOT NULL DEFAULT 0,
      saved_points INTEGER NOT NULL DEFAULT 0,
      saved_last_seen_unix INTEGER NOT NULL DEFAULT 0
    )
    """,

    # Per-node-per-hour presence table for fast "online activity" charts.
    #
    # The UI's online-activity view needs "how many distinct nodes were seen per hour"
    # over a window. Computing this from node_metrics_1m requires scanning and
    # COUNT(DISTINCT node_id) across potentially large history.
    #
    # node_hour_seen is maintained incrementally via triggers on node_metrics_1m
    # and stays ~60x smaller than the 1-minute rollup.
    """
    CREATE TABLE IF NOT EXISTS node_hour_seen (
      hour_bucket INTEGER NOT NULL,
      node_id TEXT NOT NULL,
      PRIMARY KEY(hour_bucket, node_id)
    )
    """,
]
