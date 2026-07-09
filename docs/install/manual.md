# Manual Foreground Run

Use this for a quick foreground run. If you are setting up the systemd service,
use the `/opt/meshyface` clone path in
[Recommended Systemd Service](systemd.md) instead.

Clone and create the virtual environment:

```bash
git clone https://github.com/jaronmcd/meshyface.git meshyface
cd meshyface
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run with Wi-Fi/TCP radio:

```bash
python mesh_dashboard.py \
  --mesh-host 192.168.1.42 \
  --mesh-tcp-port 4403 \
  --http-host 0.0.0.0 \
  --http-port 8877 \
  --refresh-ms 3000
```

Replace `192.168.1.42` with the Wi-Fi IP address of your radio.

Run with USB serial radio:

```bash
python mesh_dashboard.py \
  --mesh-port /dev/ttyACM0 \
  --http-host 0.0.0.0 \
  --http-port 8877 \
  --refresh-ms 3000
```

Use `/dev/serial/by-id/...` for a stable serial path when possible.

Open the UI:

- Local: `http://127.0.0.1:8877`
- LAN: `http://<host-ip>:8877`

Run `python mesh_dashboard.py --help` for the authoritative runtime flag list.
