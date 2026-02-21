import argparse

from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface


def main() -> None:
    parser = argparse.ArgumentParser(description="Show basic Meshtastic connection details.")
    add_mesh_connection_args(parser)
    args = parser.parse_args()

    print(f"Connected on: {mesh_target_label(args)}")
    iface = open_mesh_interface(args)
    try:
        print("myInfo:", iface.myInfo)

        local = iface.getNode("^local")
        local_num = local.nodeNum  # <-- correct attribute

        # nodeId string lives in the node DB, not on Node object
        local_info = (iface.nodesByNum or {}).get(local_num, {})
        local_id = local_info.get("user", {}).get("id", f"!{local_num:08x}")

        print("Local nodeNum:", local_num)
        print("Local nodeId:", local_id)
        print("Known nodes:", len(iface.nodes or {}))
        print("Some node IDs:", list((iface.nodes or {}).keys())[:10])
    finally:
        iface.close()


if __name__ == "__main__":
    main()
