# Meshyface Public (core-ui)

Meshyface is a chat-first Meshtastic web dashboard for LAN-hosted operation.

This branch (`release/public-v0`) is the curated public surface. It is focused on stable daily use and intentionally omits several experimental/private modules.

## What Public Includes

Public `core-ui` includes:

- Chat workspace (`Everyone`, direct peer workflow, send box, reply/ack actions)
- Network map (nodes, heatmap, packet lines, node selection)
- Node-focused map behavior (one-shot snap, history trail focus, clean reset fallback when no location)
- Console panel
- Settings workspace (radio/dashboard controls, channels, tickers, appearance, data)
- Persisted SQLite history backing map/chat/node context

## What Public Does Not Include (By Design)

These surfaces are hidden/disabled in `core-ui`:

- Apps workspace (files/games/remote/BBS workflows)
- Bots workspace
- Labs workspace
- Dedicated Sensors and History rail workspaces from full profile

That separation is intentional so public stays lean and predictable.

## Requirements

- Linux host strongly recommended for server mode
- Python 3.11+
- Meshtastic-accessible radio over either:
  - TCP (`--mesh-host` + `--mesh-tcp-port`), or
  - Serial USB (`--mesh-port`)
- Python packages:
  - `meshtastic`
  - `pypubsub`
  - `protobuf`

## Repository Layout

- `mesh_dashboard.py` - dashboard entrypoint
- `mesh_connection.py` - Meshtastic TCP/serial connection handling
- `meshdash/` - backend modules and frontend templates
- `scripts/deploy_dashboard.sh` - remote deploy/bootstrap helper
- `scripts/release_public.sh` - curated public release packager

## Standalone Install (Single Machine)

### 1) Clone + venv

```bash
git clone <your-repo-url> meshyface
cd meshyface
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install meshtastic pypubsub protobuf
```

### 2A) Run with Wi-Fi/TCP radio

```bash
python mesh_dashboard.py \
  --mesh-host 192.168.1.69 \
  --mesh-tcp-port 4403 \
  --http-host 0.0.0.0 \
  --http-port 8877 \
  --refresh-ms 3000
```

### 2B) Run with USB serial radio

```bash
python mesh_dashboard.py \
  --mesh-port /dev/ttyACM0 \
  --http-host 0.0.0.0 \
  --http-port 8877 \
  --refresh-ms 3000
```

Tip: use `/dev/serial/by-id/...` for a stable serial path when possible.

### 3) Open UI

- Local: `http://127.0.0.1:8877`
- LAN: `http://<host-ip>:8877`

## Proxmox Deep Dive

You have two common deployment models:

1. Proxmox VM/LXC + radio reachable over LAN (TCP) - easiest and most stable.
2. Proxmox VM/LXC + USB radio passthrough (serial) - works, but needs device passthrough.

### Recommended: Proxmox with TCP radio

If your radio is on Wi-Fi/Ethernet and exposes TCP (usually `4403`), run the dashboard in a VM or container and connect over network.

#### Fast bootstrap/deploy from your workstation

From this repo:

```bash
./scripts/deploy_dashboard.sh \
  --target j@192.168.1.241 \
  --bootstrap \
  --mesh-host 192.168.1.69 \
  --mesh-port 4403 \
  --ui-profile core-ui \
  --clean-app-dir
```

This installs runtime, deploys app files, writes `dashboard.env`, and restarts the service.

#### Update loop

```bash
./scripts/deploy_dashboard.sh \
  --target j@192.168.1.241 \
  --mesh-host 192.168.1.69 \
  --mesh-port 4403 \
  --ui-profile core-ui \
  --clean-app-dir
```

### Proxmox with USB serial radio

#### VM path

- In Proxmox GUI: VM -> Hardware -> Add -> USB Device
- Boot VM and confirm device appears:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
ls -l /dev/serial/by-id 2>/dev/null
```

#### LXC path (advanced)

For LXC, pass serial device from host into container config (exact lines vary by host/device). Typical pattern:

- allow character device
- bind-mount `/dev/ttyACM0` (or `/dev/ttyUSB0`) into container

After passthrough, verify same `ls` commands inside container.

### Run as systemd service (TCP)

The included `meshtastic-dashboard.service` is wired for TCP mode and reads env from `/home/j/mesh/config/dashboard.env`.

Example env:

```bash
cat > /home/j/mesh/config/dashboard.env <<'EOF_ENV'
MESH_HOST=192.168.1.69
MESH_PORT=4403
DASH_HOST=0.0.0.0
DASH_PORT=8877
REFRESH_MS=3000
MESH_DASH_UI_PROFILE=core-ui
MESH_DASH_HISTORY_DB=/home/j/mesh/mesh_dashboard_history.sqlite3
MESH_DASH_FILE_TRANSFER_ENABLE=0
MESH_DASH_FILE_TRANSFER_MAX_BYTES=12288
MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=0
PYTHONUNBUFFERED=1
EOF_ENV
```

Start/restart:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-dashboard
sudo systemctl restart meshtastic-dashboard
sudo systemctl status meshtastic-dashboard --no-pager
```

### Run as systemd service (serial)

For serial mode, change `ExecStart` to use `--mesh-port` instead of `--mesh-host`.

Quick override:

```bash
sudo systemctl edit meshtastic-dashboard
```

Drop-in contents:

```ini
[Service]
ExecStart=
ExecStart=/home/j/mesh/.venv/bin/python /home/j/mesh/app/mesh_dashboard.py --mesh-port /dev/ttyACM0 --http-host ${DASH_HOST} --http-port ${DASH_PORT} --refresh-ms ${REFRESH_MS}
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart meshtastic-dashboard
```

Also ensure service user can access serial device (usually `dialout` group).

### File transfer safety gate (CLI + service)

File transfer is hidden/disabled by default. To enable it you must set both:

- `--file-transfer-enable` (or `MESH_DASH_FILE_TRANSFER_ENABLE=1`)
- disclaimer acceptance:
  `--accept-file-transfer-traffic-disclaimer` (or `MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER=1`)

Optional size cap:

- `--file-transfer-max-bytes <bytes>` (or `MESH_DASH_FILE_TRANSFER_MAX_BYTES=<bytes>`)
- Valid range is clamped to `1024` .. `512000` bytes.

Deploy helper example (service mode, file transfer enabled):

```bash
./scripts/deploy_dashboard.sh \
  --target j@192.168.1.241 \
  --mesh-host 192.168.1.69 \
  --file-transfer-enable \
  --file-transfer-max-bytes 512000 \
  --accept-file-transfer-traffic-disclaimer \
  --clean-app-dir
```

Note: `scripts/deploy_dashboard.sh` preserves existing file-transfer env values from the target `dashboard.env` unless you explicitly pass file-transfer flags/env overrides.

In the Files panel, use `Clear finished` (next to console `Copy`/`Clear`) to remove completed/failed transfer rows from the current dashboard session.

## Configuration Reference

Primary runtime flags:

- `--mesh-host <ip-or-dns>`: TCP radio host
- `--mesh-tcp-port <port>`: TCP radio port (default `4403`)
- `--mesh-port <path>`: serial device path
- `--http-host <host>`: bind host (default `0.0.0.0`)
- `--http-port <port>`: bind port (default `8877`)
- `--refresh-ms <ms>`: browser poll interval (default `3000`)
- `--history-db <path>`: SQLite DB path
- `--no-history`: memory-only mode
- `--private-mode`: hide/disable public chat surfaces
- `--api-token <token>`: require token for write APIs
- `--file-transfer-enable/--no-file-transfer-enable`: toggle file transfer feature
- `--file-transfer-max-bytes <bytes>`: file transfer upload cap
- `--accept-file-transfer-traffic-disclaimer`: required when enabling file transfer

Environment variables commonly used in service mode:

- `MESH_HOST`
- `MESH_PORT` (used as TCP port in provided service)
- `DASH_HOST`
- `DASH_PORT`
- `REFRESH_MS`
- `MESH_DASH_UI_PROFILE` (`core-ui` for public branch)
- `MESH_DASH_HISTORY_DB`
- `PYTHONUNBUFFERED`
- Optional: `MESH_DASH_PRIVATE_MODE`, `MESH_DASH_API_TOKEN`
- Optional: `MESH_DASH_FILE_TRANSFER_ENABLE`
- Optional: `MESH_DASH_FILE_TRANSFER_MAX_BYTES`
- Optional: `MESH_DASH_ACCEPT_FILE_TRANSFER_TRAFFIC_DISCLAIMER`

## Public Branch Workflow Notes

- Main private development branch can move faster.
- `release/public-v0` is curated for public stability.
- Public release packaging is allowlist-driven via `scripts/release_public.sh`.

Useful checks:

```bash
./scripts/check_public_branch_drift.sh --public-branch release/public-v0 --base-branch main
./scripts/release_public.sh --source-branch release/public-v0 --dry-run
```

## Operations and Troubleshooting

Service health:

```bash
sudo systemctl status meshtastic-dashboard --no-pager
sudo journalctl -u meshtastic-dashboard -f
```

HTTP health/version:

```bash
curl -s http://127.0.0.1:8877/api/health
curl -s http://127.0.0.1:8877/api/version
```

If serial mode fails:

```bash
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
ls -l /dev/serial/by-id 2>/dev/null
groups
```

If UI looks stale after deploy, hard refresh browser (`Ctrl+Shift+R`).

## Security

- This dashboard is intended for trusted LAN/VPN environments.
- Do not expose directly to the public internet without a reverse proxy and access control.
- Use `--private-mode` and/or `--api-token` for stricter write-path control.
