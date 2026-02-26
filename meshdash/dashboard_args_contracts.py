from typing import Protocol


class DashboardArgs(Protocol):
    history_db: str
    no_history: bool
    history_max_rows: int
    history_retention_days: int
    history_event_max_rows: int
    history_event_retention_days: int
    history_rollup_retention_days: int
    packet_limit: int
    show_secrets: bool
    node_history_hours: int
    node_history_max_points: int
    refresh_ms: int
    http_host: str
    http_port: int
