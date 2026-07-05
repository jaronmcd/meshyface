import socket
from typing import Callable, Optional, Protocol

from .revision import RevisionInfo
from .runtime_lifecycle_contracts import CloseableResource, RuntimeServer


class UdpSocketLike(Protocol):
    def __enter__(self) -> "UdpSocketLike":
        ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        ...

    def connect(self, address: tuple[str, int]) -> None:
        ...

    def getsockname(self) -> tuple[str, int]:
        ...


class SocketModuleLike(Protocol):
    AF_INET: int
    SOCK_DGRAM: int
    gaierror: type[BaseException]

    def socket(self, family: int, socktype: int) -> UdpSocketLike:
        ...

    def gethostname(self) -> str:
        ...

    def getaddrinfo(
        self,
        hostname: str,
        service: object,
        *,
        family: int | None = None,
    ) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        ...


def guess_lan_ipv4(socket_module: SocketModuleLike = socket) -> Optional[str]:
    try:
        with socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        addr_info = socket_module.getaddrinfo(
            socket_module.gethostname(),
            None,
            family=socket_module.AF_INET,
        )
        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            if ip and not ip.startswith("127."):
                return ip
    except socket_module.gaierror:
        pass

    return None


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
    out_fn(f"Revision: {revision_info.label}")

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
    try:
        server.server_close()
    except Exception:
        pass
    try:
        iface.close()
    except Exception:
        pass
    if history_store is not None:
        try:
            history_store.close()
        except Exception:
            pass
