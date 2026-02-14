import meshtastic.serial_interface

PORT = "/dev/ttyUSB2"

iface = meshtastic.serial_interface.SerialInterface(devPath=PORT)

print("Connected on:", PORT)
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

iface.close()
