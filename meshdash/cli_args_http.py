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
        default=False,
        help=(
            "Allow the sensitive raw-packet database download without an API token "
            "for direct loopback clients only (default: False)."
        ),
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
