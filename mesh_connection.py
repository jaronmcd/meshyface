import argparse

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


def open_mesh_interface(args: argparse.Namespace):
    if _meshtastic_serial_interface is None or _meshtastic_tcp_interface is None:
        raise RuntimeError(
            "meshtastic Python package is required. Install with: pip install meshtastic"
        )
    if getattr(args, "mesh_host", None):
        return _meshtastic_tcp_interface.TCPInterface(
            hostname=args.mesh_host,
            portNumber=args.mesh_tcp_port,
        )
    return _meshtastic_serial_interface.SerialInterface(devPath=args.mesh_port)


def mesh_target_label(args: argparse.Namespace) -> str:
    if getattr(args, "mesh_host", None):
        return f"{args.mesh_host}:{args.mesh_tcp_port} (tcp)"
    return f"{args.mesh_port} (serial)"
