import meshtastic.serial_interface

DEST = "!ba4bf9d0"   # replace with a real nodeId you see in iface.nodes keys

iface = meshtastic.serial_interface.SerialInterface(devPath="/dev/ttyACM0")

# Ask for ack so you know it was delivered (or retried and failed)
iface.sendText("ping from python (DM)", destinationId=DEST, wantAck=True)

iface.close()
