import time
from pubsub import pub
import meshtastic.serial_interface

def on_receive(packet, interface):
    # packet is a dict; print it raw to learn the structure for your use-case
    print("\n--- PACKET ---")
    print(packet)

def on_text(packet, interface):
    # Text packets typically have a decoded.text field
    text = packet.get("decoded", {}).get("text")
    frm = packet.get("fromId")
    print(f"\nTEXT from {frm}: {text}")

def on_connection(interface, topic=pub.AUTO_TOPIC):
    print("Connected.")
    print("Local myInfo:", interface.myInfo)     # local radio identity/IDs :contentReference[oaicite:5]{index=5}
    print(f"Known nodes so far: {len(interface.nodes)}")  # node DB :contentReference[oaicite:6]{index=6}

pub.subscribe(on_receive, "meshtastic.receive")
pub.subscribe(on_text, "meshtastic.receive.text")
pub.subscribe(on_connection, "meshtastic.connection.established")

iface = meshtastic.serial_interface.SerialInterface(devPath="/dev/ttyACM0")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    iface.close()
