# Proxmox USB Meshtastic Gateway (RAK4631 or Heltec V3)

This setup exposes a USB Meshtastic node as a TCP endpoint (like a LAN "radio server").

- Works with `RAK4631` and `Heltec V3` when running Meshtastic firmware.
- Client app/CLI connects to `<guest-ip>:4403` over TCP.
- One active TCP client at a time is recommended.

## 1) Pick VM or LXC

Use a Debian VM or privileged LXC that can see the USB serial device.

## 2) Pass USB into Proxmox guest

### Option A: QEMU VM passthrough (recommended)

On Proxmox host:

```bash
lsusb
```

Find your device vendor/product ID, then attach to VM:

```bash
qm set <VMID> -usb0 host=<VENDOR_ID>:<PRODUCT_ID>
```

Example:

```bash
qm set 101 -usb0 host=10c4:ea60
```

Reboot VM (or power-cycle VM device settings) and verify in guest:

```bash
ls -l /dev/serial/by-id/
```

### Option B: LXC passthrough

For `ttyACM*` devices:

```ini
lxc.cgroup2.devices.allow: c 166:* rwm
lxc.mount.entry: /dev/ttyACM0 dev/ttyACM0 none bind,optional,create=file
```

For `ttyUSB*` devices:

```ini
lxc.cgroup2.devices.allow: c 188:* rwm
lxc.mount.entry: /dev/ttyUSB0 dev/ttyUSB0 none bind,optional,create=file
```

Then restart the container and verify device exists inside it.

## 3) Install runtime in guest

```bash
sudo apt update
sudo apt install -y python3 python3-venv
```

Copy `meshtastic_usb_gateway.py` into guest, e.g. `/opt/meshtastic-gateway/`.

```bash
sudo mkdir -p /opt/meshtastic-gateway
sudo cp meshtastic_usb_gateway.py /opt/meshtastic-gateway/
sudo chmod +x /opt/meshtastic-gateway/meshtastic_usb_gateway.py
```

Install pyserial:

```bash
sudo apt install -y python3-serial
```

## 4) Manual test

Use the stable by-id path:

```bash
ls -l /dev/serial/by-id/
```

Start gateway:

```bash
sudo python3 /opt/meshtastic-gateway/meshtastic_usb_gateway.py \
  --serial /dev/serial/by-id/<YOUR_RADIO_ID> \
  --listen-host 0.0.0.0 \
  --listen-port 4403
```

From another machine:

```bash
meshtastic --host <GUEST_IP> --info
```

Or in your app, choose TCP and connect to `<GUEST_IP>:4403`.

## 5) Run as systemd service

Copy unit file:

```bash
sudo cp meshtastic-usb-gateway.service /etc/systemd/system/
```

Edit service `ExecStart` serial path:

```bash
sudo nano /etc/systemd/system/meshtastic-usb-gateway.service
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-usb-gateway
sudo systemctl status meshtastic-usb-gateway
```

Logs:

```bash
journalctl -u meshtastic-usb-gateway -f
```

## 6) Firewall

Allow TCP 4403 only from trusted LAN/VPN ranges.

Example (UFW):

```bash
sudo ufw allow from 192.168.1.0/24 to any port 4403 proto tcp
```

## 7) Notes for RAK4631 vs Heltec V3

- RAK4631 often appears as `/dev/ttyACM*`.
- Heltec V3 often appears as `/dev/ttyUSB*`.
- Always prefer `/dev/serial/by-id/...` in service config.
- Ensure Meshtastic `serial_enabled` is true on the node.
