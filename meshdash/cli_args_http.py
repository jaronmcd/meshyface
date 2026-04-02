import argparse


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
        default=default_api_token,
        help=(
            "Optional API token required on write endpoints via Authorization: Bearer <token> "
            "or X-API-Token header."
        ),
    )
