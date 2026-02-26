import socket
from typing import Optional, Protocol


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


class DefaultGatewayArgs(Protocol):
    no_default_gateway: bool
    mesh_host: str | None
    mesh_port: str
    default_gateway_host: str | None
    default_gateway_port: int
    mesh_tcp_port: int


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
        addr_info = socket_module.getaddrinfo(socket_module.gethostname(), None, family=socket_module.AF_INET)
        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            if ip and not ip.startswith("127."):
                return ip
    except socket_module.gaierror:
        pass

    return None


def apply_default_gateway(args: DefaultGatewayArgs, *, default_mesh_port: str) -> None:
    # If user did not provide --mesh-host and left serial at the default path,
    # prefer the shared TCP gateway for this dashboard.
    if args.no_default_gateway:
        return
    if args.mesh_host:
        return
    if args.mesh_port != default_mesh_port:
        return
    if not args.default_gateway_host:
        return
    args.mesh_host = args.default_gateway_host
    args.mesh_tcp_port = args.default_gateway_port
