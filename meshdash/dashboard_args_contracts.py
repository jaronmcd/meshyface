from typing import Protocol


class DashboardArgs(Protocol):
    history_db: str
    no_history: bool
    seed_from_node_db: bool
    history_max_rows: int
    history_retention_days: int
    history_event_max_rows: int
    history_event_retention_days: int
    history_rollup_retention_days: int
    packet_limit: int
    show_secrets: bool
    debug_mode: bool
    node_history_hours: int
    node_history_max_points: int
    refresh_ms: int
    reset_ticker_scale_on_restart: bool
    http_host: str
    http_port: int
    allow_tokenless_raw_packet_download: bool
    plugins_enable: bool
    plugins_directory: str
    plugins_state_db: str
    plugins_files_directory: str
    plugins_handler_timeout: float
    plugins_event_queue_size: int
    plugin_enable: list[str]
    plugin_disable: list[str]
    games_enable: bool
