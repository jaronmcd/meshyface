from typing import Callable, Optional

from .revision import RevisionInfo
from .runtime_lifecycle_contracts import CloseableResource, RuntimeServer


def emit_startup_status(
    *,
    http_host: str,
    bound_host: str,
    bound_port: int,
    show_secrets: bool,
    revision_info: RevisionInfo,
    history_enabled: bool,
    history_db_path: str,
    history_retention_days: int,
    history_max_rows: int,
    history_event_retention_days: int,
    history_event_max_rows: int,
    history_rollup_retention_days: int,
    guess_lan_ipv4_fn: Callable[[], Optional[str]],
    out_fn: Callable[[str], None] = print,
) -> None:
    out_fn("Dashboard server running.")
    out_fn(f"Bound to: {bound_host}:{bound_port}")
    if http_host in ("0.0.0.0", "::"):
        out_fn(f"Open from this computer: http://127.0.0.1:{bound_port}")
        lan_ip = guess_lan_ipv4_fn()
        if lan_ip:
            out_fn(f"Open from Wi-Fi devices: http://{lan_ip}:{bound_port}")
        else:
            out_fn(f"Open from Wi-Fi devices: http://<this-computer-ip>:{bound_port}")
    else:
        out_fn(f"Open: http://{http_host}:{bound_port}")

    if not show_secrets:
        out_fn("Secrets are redacted. Use --show-secrets to display full values.")
    out_fn(f"Revision: v{revision_info.version} ({revision_info.commit})")

    if history_enabled:
        out_fn(
            f"History DB: {history_db_path} "
            f"(retention {history_retention_days}d, max {history_max_rows} rows; "
            f"events {history_event_retention_days}d/{history_event_max_rows} rows; "
            f"rollups {history_rollup_retention_days}d)"
        )
    else:
        out_fn("History DB: disabled")
    out_fn("Press Ctrl+C to stop.")


def serve_until_stopped(
    server: RuntimeServer,
    *,
    poll_interval: float = 0.5,
    out_fn: Callable[[str], None] = print,
) -> None:
    try:
        server.serve_forever(poll_interval=poll_interval)
    except KeyboardInterrupt:
        out_fn("Stopping dashboard...")


def close_runtime_resources(
    *,
    server: RuntimeServer,
    iface: CloseableResource,
    history_store: Optional[CloseableResource],
) -> None:
    server.server_close()
    iface.close()
    if history_store is not None:
        history_store.close()
