import argparse


class _ApiTokenAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        del parser, option_string
        setattr(namespace, self.dest, values)
        setattr(namespace, "api_token_supplied_via_cli", True)


class _IgnoredCompatibilityFlag(argparse.Action):
    def __init__(self, option_strings: list[str], dest: str, **kwargs: object) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        del parser, namespace, values, option_string


def add_http_runtime_args(
    parser: argparse.ArgumentParser,
    *,
    default_http_host: str,
    default_http_port: int,
    default_refresh_ms: int,
    default_packet_limit: int,
    default_reset_ticker_scale_on_restart: bool = True,
    default_private_mode: bool = False,
    default_api_token: str | None = None,
    default_file_transfer_enable: bool = False,
    default_file_transfer_auto_accept: bool = False,
    default_bots_enable: bool = False,
    default_bots_directory: str = "mesh_dashboard_plugins",
    default_bots_state_db: str = "mesh_dashboard_plugin_state.sqlite3",
    default_bots_files_directory: str = "mesh_dashboard_plugin_files",
    default_bots_handler_timeout: float = 5.0,
    default_bots_event_queue_size: int = 128,
    default_bot_enable: list[str] | None = None,
    default_bot_disable: list[str] | None = None,
    default_games_enable: bool = False,
    default_file_transfer_max_bytes: int = 64 * 1024,
    default_accept_file_transfer_traffic_disclaimer: bool = False,
) -> None:
    parser.set_defaults(api_token_supplied_via_cli=False)
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
        "--reset-ticker-scale-on-restart",
        action=argparse.BooleanOptionalAction,
        default=default_reset_ticker_scale_on_restart,
        help=(
            "Reset top ticker trend scales when the live packet counter restarts "
            f"(default: {default_reset_ticker_scale_on_restart})"
        ),
    )
    parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Display sensitive config values (private keys/passwords/PSKs) in raw JSON panels.",
    )
    parser.add_argument(
        "--debug-mode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Expose debug-only dashboard surfaces such as advanced diagnostics tabs "
            "(default: False)"
        ),
    )
    parser.add_argument(
        "--private-mode",
        action=argparse.BooleanOptionalAction,
        default=default_private_mode,
        help=(
            "Disable public chat/message API surfaces for sensitive deployments "
            f"(default: {default_private_mode})"
        ),
    )
    parser.add_argument(
        "--api-token",
        action=_ApiTokenAction,
        default=default_api_token,
        help=(
            "Optional API token required on write endpoints via Authorization: Bearer <token> "
            "or X-API-Token header. Prefer MESH_DASH_API_TOKEN on shared hosts; "
            "command-line tokens may appear in process listings and shell history."
        ),
    )
    parser.add_argument(
        "--allow-tokenless-raw-packet-download",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Allow the sensitive raw-packet database download without an API token "
            "for loopback and private-LAN clients (default: True)."
        ),
    )
    # Keep existing service definitions restartable after BBS removal. These
    # switches intentionally create no Namespace value and enable nothing.
    parser.add_argument(
        "--bbs-enable",
        "--no-bbs-enable",
        action=_IgnoredCompatibilityFlag,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--file-transfer-enable",
        action=argparse.BooleanOptionalAction,
        default=default_file_transfer_enable,
        help=(
            "Enable Meshyface peer-to-peer file transfer UI and send workflow "
            f"(default: {default_file_transfer_enable})"
        ),
    )
    parser.add_argument(
        "--file-transfer-auto-accept",
        action=argparse.BooleanOptionalAction,
        default=default_file_transfer_auto_accept,
        help=(
            "Automatically accept direct inbound Meshyface file transfers in the "
            "backend, and use the same value as the browser preference default "
            f"(default: {default_file_transfer_auto_accept})"
        ),
    )
    parser.add_argument(
        "--bots-enable",
        action=argparse.BooleanOptionalAction,
        default=default_bots_enable,
        help=(
            "Enable the trusted Python plugin subsystem "
            f"(default: {default_bots_enable})"
        ),
    )
    parser.add_argument(
        "--bots-directory",
        default=default_bots_directory,
        help="Persistent directory containing local bot plugin packages.",
    )
    parser.add_argument(
        "--bots-state-db",
        default=default_bots_state_db,
        help="Independent SQLite database for bot state, sessions, and enablement.",
    )
    parser.add_argument(
        "--bots-files-directory",
        default=default_bots_files_directory,
        help="Approved root for files requested through the bot API.",
    )
    parser.add_argument(
        "--bots-handler-timeout",
        type=float,
        default=default_bots_handler_timeout,
        help="Maximum seconds allowed for one bot handler.",
    )
    parser.add_argument(
        "--bots-event-queue-size",
        type=int,
        default=default_bots_event_queue_size,
        help="Maximum pending normalized bot events.",
    )
    parser.add_argument(
        "--bot-enable",
        action="append",
        default=list(default_bot_enable or ()),
        metavar="ID",
        help="Enable one discovered bot ID; may be repeated.",
    )
    parser.add_argument(
        "--bot-disable",
        action="append",
        default=list(default_bot_disable or ()),
        metavar="ID",
        help="Disable one discovered bot ID; may be repeated.",
    )
    parser.add_argument(
        "--games-enable",
        action=argparse.BooleanOptionalAction,
        default=default_games_enable,
        help=(
            "Enable local games and standalone Zork console endpoints "
            f"(default: {default_games_enable})"
        ),
    )
    parser.add_argument(
        "--file-transfer-max-bytes",
        type=int,
        default=default_file_transfer_max_bytes,
        help=(
            "Maximum file size allowed by the dashboard file transfer UI in bytes "
            f"(default: {default_file_transfer_max_bytes})"
        ),
    )
    parser.add_argument(
        "--accept-file-transfer-traffic-disclaimer",
        action=argparse.BooleanOptionalAction,
        default=default_accept_file_transfer_traffic_disclaimer,
        help=(
            "Acknowledge that enabling file transfer can significantly "
            "increase mesh airtime and congestion. "
            f"(default: {default_accept_file_transfer_traffic_disclaimer})"
        ),
    )
