import json
import meshtastic.serial_interface

iface = meshtastic.serial_interface.SerialInterface(devPath="/dev/ttyACM0")

print(f"{len(iface.nodes)} nodes (by nodeId):")
for node_id, info in iface.nodes.items():
    print("\nNODE:", node_id)
    # info might contain nested dicts; default=str makes it printable even if types vary
    print(json.dumps(info, indent=2, default=str))

iface.close()
