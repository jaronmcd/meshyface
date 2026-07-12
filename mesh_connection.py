import argparse
import ipaddress

try:
    import meshtastic.serial_interface as _meshtastic_serial_interface
    import meshtastic.tcp_interface as _meshtastic_tcp_interface
except Exception:
    _meshtastic_serial_interface = None
    _meshtastic_tcp_interface = None

from meshdash.config import DEFAULT_MESH_PORT

DEFAULT_MESH_TCP_PORT = 4403


def add_mesh_connection_args(
    parser: argparse.ArgumentParser, *, default_mesh_port: str = DEFAULT_MESH_PORT
) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--mesh-port",
        default=default_mesh_port,
        help=f"Serial port for your radio (default: {default_mesh_port})",
    )
    group.add_argument(
        "--mesh-host",
        help="Connect to a Meshtastic device over TCP by host/IP (e.g. 192.0.2.10).",
    )
    parser.add_argument(
        "--mesh-tcp-port",
        type=int,
        default=DEFAULT_MESH_TCP_PORT,
        help=f"TCP port for --mesh-host mode (default: {DEFAULT_MESH_TCP_PORT})",
    )
    parser.add_argument(
        "--allow-insecure-mesh-tcp",
        action="store_true",
        help=(
            "Allow an unauthenticated Meshtastic TCP connection to a non-loopback host. "
            "Use only through a trusted VPN or SSH tunnel."
        ),
    )


def _is_loopback_host(value: object) -> bool:
    host = str(value or "").strip().lower()
    if host in {"localhost", "localhost.localdomain"}:
        return True
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        return bool(ipaddress.ip_address(host).is_loopback)
    except ValueError:
        return False


def open_mesh_interface(args: argparse.Namespace):
    if _meshtastic_serial_interface is None or _meshtastic_tcp_interface is None:
        raise RuntimeError(
            "meshtastic Python package is required. Install with: pip install meshtastic"
        )
    if getattr(args, "mesh_host", None):
        if not _is_loopback_host(args.mesh_host) and not bool(
            getattr(args, "allow_insecure_mesh_tcp", False)
        ):
            raise RuntimeError(
                "Refusing unauthenticated Meshtastic TCP to a non-loopback host. "
                "Use a trusted VPN/SSH tunnel or explicitly pass --allow-insecure-mesh-tcp."
            )
        return _meshtastic_tcp_interface.TCPInterface(
            hostname=args.mesh_host,
            portNumber=args.mesh_tcp_port,
        )
    return _meshtastic_serial_interface.SerialInterface(devPath=args.mesh_port)


def mesh_target_label(args: argparse.Namespace) -> str:
    if getattr(args, "mesh_host", None):
        return f"{args.mesh_host}:{args.mesh_tcp_port} (tcp)"
    return f"{args.mesh_port} (serial)"
