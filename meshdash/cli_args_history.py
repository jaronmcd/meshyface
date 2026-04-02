import argparse


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
    parser.add_argument(
        "--seed-from-node-db",
        action="store_true",
        help=(
            "Seed live tracker from connected radio NodeDB at startup. "
            "Disabled by default to avoid stale carry-over heatmap/state."
        ),
    )
    parser.add_argument(
        "--backfill-environment-rollups",
        action="store_true",
        help=(
            "One-shot mode: backfill environment_metrics_1m from saved packet history "
            "and exit (no dashboard server)."
        ),
    )
    parser.add_argument(
        "--backfill-environment-rollups-reset",
        action="store_true",
        help=(
            "When used with --backfill-environment-rollups, clear existing "
            "environment_metrics_1m rows before rebuilding."
        ),
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
