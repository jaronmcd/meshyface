import argparse

from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one broadcast Meshtastic message.")
    add_mesh_connection_args(parser)
    parser.add_argument(
        "--text",
        default="hello mesh from python",
        help="Text payload to send.",
    )
    args = parser.parse_args()

    print(f"Connecting to {mesh_target_label(args)} ...")
    iface = open_mesh_interface(args)
    try:
        iface.sendText(args.text)

        local = iface.getNode("^local")
        print("Local config:", local.localConfig)
    finally:
        iface.close()


if __name__ == "__main__":
    main()
