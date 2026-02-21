import argparse

import meshtastic.serial_interface
import meshtastic.tcp_interface


DEFAULT_MESH_PORT = "/dev/ttyACM0"
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
        help="Connect to a Meshtastic device over TCP by host/IP (e.g. 192.168.1.234).",
    )
    parser.add_argument(
        "--mesh-tcp-port",
        type=int,
        default=DEFAULT_MESH_TCP_PORT,
        help=f"TCP port for --mesh-host mode (default: {DEFAULT_MESH_TCP_PORT})",
    )


def open_mesh_interface(args: argparse.Namespace):
    if getattr(args, "mesh_host", None):
        return meshtastic.tcp_interface.TCPInterface(
            hostname=args.mesh_host,
            portNumber=args.mesh_tcp_port,
        )
    return meshtastic.serial_interface.SerialInterface(devPath=args.mesh_port)


def mesh_target_label(args: argparse.Namespace) -> str:
    if getattr(args, "mesh_host", None):
        return f"{args.mesh_host}:{args.mesh_tcp_port} (tcp)"
    return f"{args.mesh_port} (serial)"
