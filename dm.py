import argparse

from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface


DEFAULT_DEST = "!ba4bf9d0"
DEFAULT_TEXT = "ping from python (DM)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a direct Meshtastic message (DM).")
    add_mesh_connection_args(parser)
    parser.add_argument(
        "--dest",
        default=DEFAULT_DEST,
        help=f"Destination node ID (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--text",
        default=DEFAULT_TEXT,
        help="Text payload to send.",
    )
    args = parser.parse_args()

    print(f"Connecting to {mesh_target_label(args)} ...")
    iface = open_mesh_interface(args)
    try:
        iface.sendText(args.text, destinationId=args.dest, wantAck=True)
        print(f"Sent to {args.dest}")
    finally:
        iface.close()


if __name__ == "__main__":
    main()
