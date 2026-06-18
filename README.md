# Meshyface

Meshyface is a chat-first Meshtastic dashboard that runs as a single Python
service and serves a single-page web UI over HTTP.



## Current App Surface

The current UI exposes:

- Chat plus direct-peer conversations
- Network workspace for map, topology, Top 10 rankings, node details, and
  on-demand history views
- Console workspace for live packet/log output
- Apps workspace with Games, plus BBS and Files tabs when those features are
  enabled
- Settings workspace with radio, device, connectivity, location, channels,
  tickers, lists, appearance, and about panes
- SQLite-backed history, search, rollups, theme persistence, and custom
  telemetry rule persistence



## Screenshots

Network workspace views from a live Meshtastic session.

### Live network map

![Live network map.](docs/screenshots/network-map.png)

Map view with node locations, links, common paths, clusters, and signal heatmap.

### Network overview

![Network overview chart.](docs/screenshots/network-overview.png)

History view for node counts, online status, new nodes, and position reports.

### Link topology

![Link topology graph.](docs/screenshots/network-links.png)

Topology view showing observed links from the selected root node.

### Route trace

![Route trace.](docs/screenshots/network-routes.png)

Trace view for a source, destination, nearby links, and per-hop packet details.

### Sensor history

![Sensor history chart.](docs/screenshots/network-sensors.png)

Telemetry chart comparing sensor history across multiple nodes.

### Status cards

![Status cards.](docs/screenshots/status-cards.png)

Top cards for radio activity, node counts, packets, links, battery, and channel
use.

## System Architecture

```mermaid
flowchart LR
  Browser["Browser<br/>single-page UI"]
  CDN["Vendored browser assets<br/>Leaflet + leaflet.heat"]
  Tiles["Basemap provider<br/>OpenStreetMap tile service"]
  Server["ThreadingHTTPServer<br/>HTML shell + JSON API"]
  Assets["Python template assembly<br/>meshdash/html* + meshdash/assets/*"]
  State["State loaders<br/>live snapshot + history readers"]
  Services["Write services<br/>chat, settings, tools, games, optional BBS/files"]
  Tracker["DashboardTracker<br/>live receive path + in-memory buffers"]
  History["HistoryStore / SQLite (WAL)<br/>chat, packets, rollups, settings"]
  Radio["Meshtastic interface<br/>serial or TCP"]
  Mesh["Meshtastic radio / mesh"]
  Atlas["Bundled offline atlas<br/>reference basemap fallback"]

  Browser -->|GET /| Server
  Browser -->|GET /api/*| Server
  Browser -->|POST write APIs| Server
  Browser --> CDN
  Browser --> Tiles
  Browser -->|fallback basemap data| Atlas
  Server --> Assets
  Server --> State
  Server --> Services
  State <--> Tracker
  State <--> History
  Services <--> History
  Services <--> Radio
  Radio <--> Mesh
  Radio -->|receive callbacks| Tracker
```

## Requirements

- Linux host strongly recommended for server mode
  - Debian-based hosts such as Raspberry Pi OS Bookworm work with the bundled
    deploy helper
- Python 3.11+
- Meshtastic-accessible radio over either:
  - TCP (`--mesh-host` + `--mesh-tcp-port`)
  - Serial USB (`--mesh-port`)
- Python packages:
  - install runtime packages with `python -m pip install -r requirements.txt`
  - install test packages with `python -m pip install -r requirements-dev.txt`
- Browser access to:
  - `https://tile.openstreetmap.org/...` if you want online basemaps

For a fully air-gapped deployment, the vendored Leaflet assets still load
locally, and the map uses the bundled offline atlas when online tile servers
are unavailable.

## Standalone Install

### 1) Clone + venv

```bash
git clone https://github.com/jaronmcd/meshyface.git meshyface
cd meshyface
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2A) Run with Wi-Fi/TCP radio

```bash
python mesh_dashboard.py \
  --mesh-host meshtastic-radio.local \
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

Run `python mesh_dashboard.py --help` for the authoritative runtime flag list.

## Docker Install

The Docker image runs the same `mesh_dashboard.py` entrypoint as the standalone
install. It stores SQLite history and theme settings under `/data` by default,
so mount a volume there if you want state to survive container replacement.

### Build image

```bash
docker build -t meshyface:local .
```

### Run with Wi-Fi/TCP radio

```bash
docker run --rm -it \
  -p 8877:8877 \
  -v meshyface-data:/data \
  -e MESH_GATEWAY_HOST=meshtastic-radio.local \
  -e MESH_GATEWAY_PORT=4403 \
  meshyface:local
```

Then open `http://127.0.0.1:8877`.

### Run with USB serial radio

```bash
docker run --rm -it \
  -p 8877:8877 \
  -v meshyface-data:/data \
  --device /dev/ttyACM0:/dev/ttyACM0 \
  -e MESH_DASH_MESH_PORT=/dev/ttyACM0 \
  meshyface:local
```

Use a stable `/dev/serial/by-id/...` host path when possible. Map it to a
container path such as `/dev/ttyACM0`, then set `MESH_DASH_MESH_PORT` to that
container path.

### Docker Compose

For a TCP radio:

```bash
MESH_GATEWAY_HOST=meshtastic-radio.local docker compose --profile tcp up -d --build
```

For a USB serial radio:

```bash
MESH_DASH_MESH_PORT=/dev/ttyACM0 docker compose --profile serial up -d --build
```

The Compose file publishes `8877`, uses the named volume `meshyface-data`, and
keeps optional BBS, games, and file-transfer features disabled unless you enable
their documented environment variables.

## Data And Storage

### Shared history database

`--history-db` is the final on-disk SQLite filename. The dashboard no longer
adds a connected-radio suffix, so any radio plugged into the dashboard
contributes to the same persisted packet, chat, node, and rollup history.

### History modes

- Default mode persists chat, packets, connection events, node analytics,
  malformed-text records, environment metrics, and summary rollups to SQLite.
- `--no-history` disables the persistent store and keeps only live in-memory
  buffers.
- Summary rollups are also sampled in the background while the dashboard is
  running when history is enabled.

### Theme and local settings

- Theme preset selection persists to
  `mesh_dashboard_theme_settings.json` by default, or the file supplied via
  `--theme-settings-file`.
- Custom telemetry rules are stored in the history SQLite database.
- BBS host settings and local BBS posts are stored in the history SQLite
  database when BBS is enabled.

### Maintenance commands

Operational commands that inspect or repair local dashboard data are documented
in [docs/maintenance.md](docs/maintenance.md).

## Links View Semantics

The `Links` subview is a topology view, not a packet-route replay.

- `History` mode draws from the stored link history saved in SQLite.
- `Live` mode draws from current-session link observations only.
- The numbered rings show shortest graph distance from the current root using a
  breadth-first search over the observed link graph.
- Those ring numbers are not literal Meshtastic forwarding hops and are not a
  real-time packet trace.
- Packet-hop metadata, when available, is still shown separately in node or
  edge details as packet-hop values.

The current root is the node the graph is centered around. Selecting a
different node changes the root and recomputes the numbered distance rings from
that node.

## Proxmox And Service Deployment

You have two common deployment models:

1. Proxmox VM/LXC + radio reachable over LAN (TCP) - simplest and most stable
2. Proxmox VM/LXC + USB radio passthrough (serial) - works, but needs device
   passthrough

### Recommended: Proxmox with TCP radio

If your radio is on Wi-Fi/Ethernet and exposes TCP (usually `4403`), run the
dashboard in a VM or container and connect over network.

#### Fast bootstrap/deploy from your workstation

From this repo:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --bootstrap \
  --mesh-host meshtastic-radio.local \
  --mesh-port 4403 \
  --clean-app-dir
```

This installs the runtime, deploys app files, writes `dashboard.env`, and
restarts the service.

Bootstrap assumptions:

- target host has `apt-get`, `systemd`, `ssh`, and `sudo`
- target Python must be `3.11+` after bootstrap; Raspberry Pi OS Bookworm is a
  good baseline
- when you do not override `MESH_DASH_DEPLOY_ROOT`, the deploy helper now uses
  the remote login user's home and installs under `<remote-home>/mesh`
- the generated service unit uses the remote login user by default and keeps
  `dialout` as the default service group for serial-access-friendly installs

Important naming note:

- In the runtime CLI, the TCP radio port flag is `--mesh-tcp-port`.
- In `scripts/deploy_meshyface.sh` and the bundled `dashboard.env`,
  `MESH_PORT` is the TCP port for historical reasons.

#### Update loop

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --mesh-host meshtastic-radio.local \
  --mesh-port 4403 \
  --clean-app-dir
```

#### Full reset + redeploy

If you want to remove the current Meshyface install on the target and rebuild it
from scratch in one step, use `--wipe-remote-root`. This removes the managed
systemd unit plus the deploy root, then bootstraps fresh:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --wipe-remote-root \
  --serial-path /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
```

`--wipe-remote-root` implies `--bootstrap`.

#### Full uninstall + hard reboot

If you want to remove Meshyface from the Pi and stop there:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --uninstall \
  --hard-reboot
```

That removes:

- `/etc/systemd/system/meshtastic-dashboard.service`
- the managed deploy root, which defaults to `/home/<ssh-user>/mesh`
- any managed app/config/log/venv/history paths that were explicitly configured
  outside the deploy root

`--hard-reboot` can also be used after a normal deploy if you want the host to
come back from a forced reboot instead of just restarting the service.

#### Raspberry Pi target

For a Raspberry Pi running Raspberry Pi OS Bookworm or newer, the same
bootstrap flow works as long as the SSH user has `sudo` access:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@raspberrypi.local \
  --bootstrap \
  --mesh-host meshtastic-radio.local \
  --mesh-port 4403 \
  --clean-app-dir
```

That will default to:

- app root: `/home/pi/mesh`
- service user: `pi`
- service group: `dialout`

If the Pi has a radio attached over USB serial instead of TCP, use the stable
`/dev/serial/by-id/...` path:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@raspberrypi.local \
  --bootstrap \
  --serial-path /dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0 \
  --clean-app-dir
```

## Configuration Reference

### Connection and transport

- `--mesh-host <ip-or-dns>`: TCP radio host
- `--mesh-tcp-port <port>`: TCP radio port, default `4403`
- `--mesh-port <path>`: serial device path
- `--default-gateway-host <host>`: fallback TCP host if `--mesh-host` is not
  provided and serial is still on the default path
- `--default-gateway-port <port>`: fallback TCP port for
  `--default-gateway-host`
- `--no-default-gateway`: force serial unless `--mesh-host` is explicitly set

Related environment variables:

- `MESH_GATEWAY_HOST`
- `MESH_GATEWAY_PORT`
- `MESH_DASH_MESH_PORT` for the default serial path

### HTTP, UI, and security

- `--http-host <host>`: bind host, default `0.0.0.0`
- `--http-port <port>`: bind port, default `8877`
- `--refresh-ms <ms>`: browser poll interval, default `3000`
- `--packet-limit <n>`: recent live packet buffer size, default `250`
- `--reset-ticker-scale-on-restart` /
  `--no-reset-ticker-scale-on-restart`
- `--show-secrets`: reveal private keys/passwords/PSKs in raw JSON panels
- `--debug-mode` / `--no-debug-mode`: expose debug-only dashboard surfaces such
  as advanced network diagnostics
- `--private-mode` / `--no-private-mode`: strip public chat slices and block
  selected public endpoints
- `--api-token <token>`: require auth on write endpoints via
  `Authorization: Bearer <token>` or `X-API-Token`
- `--bbs-enable` / `--no-bbs-enable`: expose or hide the BBS/profile workspace
  when `--accept-file-transfer-traffic-disclaimer` is also set
- `--games-enable` / `--no-games-enable`: enable playable Zork console
  endpoints plus mesh bot replies

Related environment variables:

- `MESH_DASH_PRIVATE_MODE`
- `MESH_DASH_API_TOKEN`
- `MESH_DASH_BBS_ENABLE`
- `MESH_DASH_GAMES_ENABLE`
- `MESH_DASH_VERSION`
- `MESH_DASH_GIT_COMMIT`

### History and analytics

- `--history-db <path>`: base SQLite DB path
- `--history-max-rows <n>`: default `200000`
- `--history-retention-days <days>`: default `30`, use `0` to disable age
  pruning
- `--history-event-max-rows <n>`: append-only packet event cap, default
  `200000`
- `--history-event-retention-days <days>`: default `30`
- `--history-rollup-retention-days <days>`: default `365`
- `--no-history`: memory-only mode
- `--seed-from-node-db`: bootstrap live tracker from the connected radio NodeDB
- `--backfill-environment-rollups`: rebuild environment rollups once and exit;
  see [docs/maintenance.md](docs/maintenance.md)
- `--backfill-environment-rollups-reset`: clear existing rollups before rebuild
- `--node-history-hours <hours>`: default selected-node window, default `72`
- `--node-history-max-points <n>`: max points returned by
  `/api/history/node`, default `1440`

Related environment variables:

- `MESH_DASH_HISTORY_DB`

### Themes

- `--theme-presets <json>`: optional custom theme preset file
- `--theme-preset <name>`: selected preset name
- `--theme-settings-file <json>`: persisted runtime theme selection file

Built-in presets:

- `default`
- `blue`
- `custom`

Fresh installs default to `custom` unless a persisted theme settings file or
`MESH_DASH_THEME_PRESET` selects another preset.

Related environment variables:

- `MESH_DASH_THEME_PRESETS`
- `MESH_DASH_THEME_PRESET`
- `MESH_DASH_THEME_SETTINGS_FILE`


## Security

- This dashboard is intended for trusted LAN/VPN environments.
- Do not expose it directly to the public internet without a reverse proxy and
  access control.
- Use `--private-mode` and/or `--api-token` for stricter write-path control.
- The built-in `Join Meshyface` channel preset uses an intentionally public
  shared Meshyface PSK for interoperability between users of this software. Do
  not use that public channel for private traffic.
- `--show-secrets` exposes sensitive values in raw JSON panels; do not enable
  it casually on shared displays.
- BBS and file transfer can consume significant mesh airtime. Keep them
  disabled unless you have explicitly accepted that tradeoff.
