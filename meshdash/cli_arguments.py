import argparse


def add_default_gateway_args(
    parser: argparse.ArgumentParser,
    *,
    resolved_gateway_host: str,
    resolved_gateway_port: int,
) -> None:
    parser.add_argument(
        "--default-gateway-host",
        default=resolved_gateway_host,
        help=(
            "Fallback TCP host for dashboard mode when --mesh-host is not provided "
            f"(default: {resolved_gateway_host})."
        ),
    )
    parser.add_argument(
        "--default-gateway-port",
        type=int,
        default=resolved_gateway_port,
        help=(
            "Fallback TCP port used with --default-gateway-host when --mesh-host is not provided "
            f"(default: {resolved_gateway_port})."
        ),
    )
    parser.add_argument(
        "--no-default-gateway",
        action="store_true",
        help="Disable default gateway fallback and use serial unless --mesh-host is set.",
    )


def add_http_runtime_args(
    parser: argparse.ArgumentParser,
    *,
    default_http_host: str,
    default_http_port: int,
    default_refresh_ms: int,
    default_packet_limit: int,
) -> None:
    parser.add_argument(
        "--http-host",
        default=default_http_host,
        help=f"HTTP bind host (default: {default_http_host})",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=default_http_port,
        help=f"HTTP bind port (default: {default_http_port})",
    )
    parser.add_argument(
        "--refresh-ms",
        type=int,
        default=default_refresh_ms,
        help=f"Browser polling interval in milliseconds (default: {default_refresh_ms})",
    )
    parser.add_argument(
        "--packet-limit",
        type=int,
        default=default_packet_limit,
        help=f"Recent packet history buffer size (default: {default_packet_limit})",
    )
    parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Display sensitive config values (private keys/passwords/PSKs) in raw JSON panels.",
    )


def add_history_args(
    parser: argparse.ArgumentParser,
    *,
    resolved_history_db: str,
    default_history_db: str,
    default_history_max_rows: int,
    default_history_retention_days: int,
    default_history_event_max_rows: int,
    default_history_event_retention_days: int,
    default_history_rollup_retention_days: int,
) -> None:
    parser.add_argument(
        "--history-db",
        default=resolved_history_db,
        help=f"SQLite DB path for persisted chat/packet history and rollups (default: {default_history_db})",
    )
    parser.add_argument(
        "--history-max-rows",
        type=int,
        default=default_history_max_rows,
        help=f"Max persisted rows per history table (default: {default_history_max_rows})",
    )
    parser.add_argument(
        "--history-retention-days",
        type=int,
        default=default_history_retention_days,
        help=(
            "Delete persisted rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {default_history_retention_days})"
        ),
    )
    parser.add_argument(
        "--history-event-max-rows",
        type=int,
        default=default_history_event_max_rows,
        help=(
            "Max rows for append-only packet event history "
            f"(default: {default_history_event_max_rows})"
        ),
    )
    parser.add_argument(
        "--history-event-retention-days",
        type=int,
        default=default_history_event_retention_days,
        help=(
            "Delete packet event rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {default_history_event_retention_days})"
        ),
    )
    parser.add_argument(
        "--history-rollup-retention-days",
        type=int,
        default=default_history_rollup_retention_days,
        help=(
            "Delete rollup rows older than this many days; "
            f"use 0 to disable age-based pruning (default: {default_history_rollup_retention_days})"
        ),
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Disable persisted SQLite history (memory-only live buffers).",
    )


def add_node_history_args(
    parser: argparse.ArgumentParser,
    *,
    default_node_history_hours: int,
    default_node_history_max_points: int,
) -> None:
    parser.add_argument(
        "--node-history-hours",
        type=int,
        default=default_node_history_hours,
        help=f"Default selected-node history window in hours (default: {default_node_history_hours})",
    )
    parser.add_argument(
        "--node-history-max-points",
        type=int,
        default=default_node_history_max_points,
        help=(
            "Max selected-node history points returned by /api/history/node "
            f"(default: {default_node_history_max_points})"
        ),
    )
