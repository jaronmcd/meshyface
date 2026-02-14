import meshtastic.serial_interface

# If you have only one radio plugged in, this can be blank and it will auto-detect.
# If you have multiple, set devPath explicitly (e.g. "/dev/ttyACM0").
iface = meshtastic.serial_interface.SerialInterface(devPath="/dev/ttyACM0")

iface.sendText("hello mesh from python")

local = iface.getNode("^local")
print("Local config:", local.localConfig)

iface.close()
