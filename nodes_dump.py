import argparse
import json

from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump known nodes from a Meshtastic interface.")
    add_mesh_connection_args(parser)
    args = parser.parse_args()

    print(f"Connecting to {mesh_target_label(args)} ...")
    iface = open_mesh_interface(args)
    try:
        print(f"{len(iface.nodes)} nodes (by nodeId):")
        for node_id, info in iface.nodes.items():
            print("\nNODE:", node_id)
            # info might contain nested dicts; default=str makes it printable even if types vary
            print(json.dumps(info, indent=2, default=str))
    finally:
        iface.close()


if __name__ == "__main__":
    main()
