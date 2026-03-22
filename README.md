# Meshyface (working title)

**Meshyface** is a chat‑first, LAN‑hosted web UI for Meshtastic networks.

It started life as **Meshtastic Deep Dashboard** (map + node intel + history). The direction now is:

- **Teams‑style workspace** (chat is primary).
- **90’s chatroom vibes** (explorable “rooms” that appear when you hear traffic).
- Network/map/history stays in the same window as contextual intelligence.

The runtime is still the same simple entrypoint: `mesh_dashboard.py`.

## Project Direction

This project is moving toward a **Teams-like mesh chat experience** where chat is primary and map/node/history panels act as contextual intelligence in the same window.

Planning docs:

- `docs/PROJECT_PLAN.md`
- `docs/ROADMAP.md` (milestones + handoff plan)
- `docs/ROOMS_SPEC.md` (rooms protocol + UX rules)
- `docs/REPO_STRUCTURE.md`

## Milestones (UI Direction)

- [x] Add Teams-style left navigation rail with view modes (`Chat`, `Network`, `Packets`, `Data`, `All`).
- [x] Add Chat-mode left expansion panel for roster-based node selection.
- [x] Add chat scopes in sidebar (`Everyone`, direct peer-to-peer).
- [ ] Add explorable public “Rooms” (AOL/Prodigy style) without spamming the normal public chat feed.
- [ ] Unify right-side contextual pane behavior (map + node history + packet context) across all views.
- [ ] Add saved view presets/layout profiles for desktop vs field testing workflows.

## What This Website Does

- Live network map with node markers and link lines.
- Click-to-select node from map, node list, or chat.
- Node history panel with signal plots (SNR/RSSI), rollup stats, and selected-node location trails.
- Name-first chat room view with send box at the bottom.
- Theme toggle (`Light`/`Dark`) that defaults to browser/system preference until user sets an explicit mode.
- Recent packets, map stats, raw config views.
- Persisted SQLite history for chat, packets, links, and node rollups.
- Top-bar host disk free indicator with green/yellow/red progress color.

## Repo Files You’ll Use

- `mesh_dashboard.py`: main web app.
- `mesh_connection.py`: serial/TCP connection helper.
- `meshdash/`: backend modules + frontend templates (HTML/CSS/JS live under `meshdash/assets/`).
- `meshtastic-dashboard.service`: systemd unit for dashboard website.
- `README.md`: setup + operations guide for this dashboard server.

Archived (not active project surface):

- `archive/scripts/`: older utility/test/support scripts.
- `archive/services/`: archived service units not used by the dashboard server.
- `archive/docs/`: archived supplemental docs.

## Requirements

- Python 3.11+ (3.13 works).
- Linux recommended for server (Debian VM works well).
- Dependencies:
  - `meshtastic`
  - `pypubsub`
  - `protobuf`

## Linux Quick Start (venv + run)

```bash
cd ~/mesh_py
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install meshtastic pypubsub protobuf
python mesh_dashboard.py --mesh-host 192.168.1.109 --mesh-tcp-port 4403 --http-host 0.0.0.0 --http-port 8877
```

Open:

- Local machine: `http://127.0.0.1:8877`
- LAN devices: `http://<your-ip>:8877`

## Windows Quick Start (PowerShell, venv + run)

This is the simple local mode: plug the Meshtastic radio into your Windows laptop,
run the backend in a terminal, and open the dashboard in a browser.

1. Open PowerShell in your repo folder.
2. Create and activate a venv.
3. Install dependencies.
4. Run the dashboard with your radio COM port.

```powershell
cd C:\meshyface\mesh_py-main
py -3 -m venv .venv
# If Activate.ps1 is blocked in this shell:
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install --upgrade pip
python -m pip install meshtastic pypubsub protobuf
python .\mesh_dashboard.py --mesh-port COM3 --http-host 0.0.0.0 --http-port 8877
```

The `python -c "import sys; print(sys.executable)"` line should print a path inside
`.venv\Scripts\python.exe`. If it does not, stop and activate the venv before installing.

Windows TCP mode (instead of USB serial):

```powershell
python .\mesh_dashboard.py --mesh-host 192.168.1.109 --mesh-tcp-port 4403 --http-host 0.0.0.0 --http-port 8877
```

No-activation option (always uses venv Python directly):

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install meshtastic pypubsub protobuf
.\.venv\Scripts\python.exe .\mesh_dashboard.py --mesh-port COM3 --http-host 0.0.0.0 --http-port 8877
```

Open:

- Local machine: `http://127.0.0.1:8877`
- Other devices on same LAN: `http://<your-laptop-ip>:8877`

Notes:

- Replace `COM3` with your actual radio port. On Windows, default serial is now `COM3` if `--mesh-port` is omitted.
- Add `--no-default-gateway` to force USB-only mode if you have `MESH_GATEWAY_HOST` set in your environment.
- This mode is intentionally terminal-run only (no Windows service/installer).

### Windows PowerShell gotchas

- `.\.venv\Scripts\Activate.ps1` is the Windows activate path.
  Linux/macOS uses `.venv/bin/activate` and will fail in PowerShell.
- If you see `pip is not recognized`, your venv is not active (or pip is not bootstrapped).
  Use `python -m pip ...` instead of plain `pip`.
- If activation is blocked, run one of:
  - `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (persistent for your user)
  - `Set-ExecutionPolicy -Scope Process Bypass` (current shell only)
- If pip is missing in the venv:
  - `python -m ensurepip --upgrade`
  - `python -m pip install --upgrade pip`

## Recommended Production Setup (Debian VM + systemd)

### 1) Create app folders on VM

```bash
mkdir -p ~/mesh/{app,config,logs}
```

### 2) Copy app files to VM (from your workstation)

⚠️ **Important:** the dashboard now depends on the `meshdash/` package directory.
Copy it alongside `mesh_dashboard.py` and `mesh_connection.py`.

```bash
scp ~/mesh_py/mesh_dashboard.py j@192.168.1.241:/home/j/mesh/app/
scp ~/mesh_py/mesh_connection.py j@192.168.1.241:/home/j/mesh/app/
scp -r ~/mesh_py/meshdash j@192.168.1.241:/home/j/mesh/app/
scp ~/mesh_py/meshtastic-dashboard.service j@192.168.1.241:/home/j/
```

### 3) Install runtime on VM

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv /home/j/mesh/.venv
/home/j/mesh/.venv/bin/pip install --upgrade pip
/home/j/mesh/.venv/bin/pip install meshtastic pypubsub protobuf
```

### 4) Configure dashboard environment on VM

```bash
cat > /home/j/mesh/config/dashboard.env <<'EOF'
MESH_HOST=192.168.1.109
MESH_PORT=4403
DASH_HOST=0.0.0.0
DASH_PORT=8877
REFRESH_MS=3000
MESH_DASH_HISTORY_DB=/home/j/mesh/mesh_dashboard_history.sqlite3
PYTHONUNBUFFERED=1
EOF
```

### 5) Install and start service

```bash
sudo cp /home/j/meshtastic-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-dashboard
sudo systemctl status meshtastic-dashboard --no-pager
```

### 6) Open the dashboard

- `http://192.168.1.241:8877`

## Fast Update/Deploy Loop

Use this after editing `mesh_dashboard.py`, `mesh_connection.py`, or `meshdash/*.py`:

```bash
chmod +x ./scripts/deploy_dashboard.sh
./scripts/deploy_dashboard.sh
```

Target is required unless `MESH_DASH_DEPLOY_TARGET` is set. For example:

```bash
./scripts/deploy_dashboard.sh --target j@192.168.1.29
```

You can still use env overrides without editing the script:

```bash
MESH_DASH_DEPLOY_TARGET=j@192.168.1.29 \
MESH_DASH_DEPLOY_APP_DIR=/home/j/mesh/app \
MESH_DASH_DEPLOY_REMOTE_PYTHON=/home/j/mesh/.venv/bin/python \
MESH_DASH_DEPLOY_SERVICE=meshtastic-dashboard \
./scripts/deploy_dashboard.sh
```

For a brand-new host (first-time setup + deploy), use bootstrap mode and set the radio IP:

```bash
./scripts/deploy_dashboard.sh \
  --target j@192.168.1.29 \
  --bootstrap \
  --mesh-host 192.168.1.211
```

Notes:

- No password is stored in the script. SSH and `sudo` will prompt as needed.
- You can also update `dashboard.env` values during deploy with options like:
  - `--mesh-port 4403`
  - `--dash-host 0.0.0.0`
  - `--dash-port 8877`
  - `--refresh-ms 3000`

Then hard refresh browser: `Ctrl+Shift+R`.

## History and Storage Behavior

By default, history is enabled and stored in SQLite (`--history-db`).

History is now profile-scoped by connected radio identity. The runtime derives a
profile key from the local radio ID (fallback: connection target) and writes to
a per-radio DB file, for example:

- base: `mesh_dashboard_history.sqlite3`
- radio profile: `mesh_dashboard_history.radio-abcdef12.sqlite3`

This isolates persisted data when you swap radios.

Important knobs:

- `--history-max-rows` (default `5000`)
- `--history-retention-days` (default `7`)
- `--history-event-max-rows` (default `200000`)
- `--history-event-retention-days` (default `30`)
- `--history-rollup-retention-days` (default `365`)
- `--node-history-hours` (default `72`)
- `--node-history-max-points` (default `1440`)
- `--no-history` disables persistence.

## Chat Send Notes

- Chat send box posts to `/api/chat/send`.
- Outgoing sends use the **Msg Ch** selector in the chat header (Meshtastic channel index).
  - Selecting **All channels (view)** only affects what you *see* in chat; outgoing sends use channel `0` in that mode.
- Message byte limit is enforced (`220` UTF-8 bytes).
- Sent messages are also echoed into dashboard chat history immediately.
- Direct peer-to-peer text messages request mesh ACK and now show delivery state (`Pending`, `Delivered`, `Failed`, `Timed out`) in chat.
- Failed direct sends can be retried from the message row using `Retry`.

## Response Bot Basics

The dashboard can now run a server-side chat responder bot (radio-wide behavior).
It listens for incoming text commands and replies on mesh via the same send pipeline.
By default, bot replies start **off**. When you turn them on, the curated startup set keeps
only `ping` and `zork` active so the Bots screen can be used as a quick “ping bot / game bot”
control surface without enabling the full catalog.

Built-in commands:

- `ping [target]`
- `zork`
- `cmd` / `help`
- `whoami`
- `whois <id|name>`
- `whohas <id|name>`
- `lheard`

Environment controls:

- `MESH_DASH_BOT_ENABLED=0|1` (default: `0`)
- `MESH_DASH_BOT_GAME_ENABLED=0|1` (default: `1`)
- `MESH_DASH_BOT_REPLY_BROADCAST=0|1` (default: `0`)
  - `0`: reply direct when request was direct, broadcast when request was broadcast
  - `1`: always broadcast replies
- `MESH_DASH_BOT_DISABLED_COMMANDS`
  - default startup profile disables every managed command except `ping` and `zork`
  - set this var explicitly to override that curated default
  - example: `MESH_DASH_BOT_DISABLED_COMMANDS=""` starts with the full managed catalog enabled
- `MESH_DASH_BOT_CUSTOM_COMMANDS` JSON object for custom commands, for example:

```bash
export MESH_DASH_BOT_CUSTOM_COMMANDS='{"status":"status local={local_id} from={from_id} hops={hops}","site":"meshface online"}'
```

Custom template fields:
`{command}`, `{args}`, `{from_id}`, `{to_id}`, `{local_id}`, `{hops}`, `{rx_time}`.

Bots panel notes:

- `Bot Commands` are backend radio behavior. Individual command toggles are preserved even when the master bot-response switch is off.
- `Bot Assistant` is browser-only UI help. Turning it off disables local Whois drafting/history matching in that browser, but manual chat commands still send normally.

## Channels (beginner-friendly docs)

Meshtastic uses the word “channel” in *multiple* ways (frequency slot vs message channel index). This dashboard exposes both.

- The `Channels` view focuses on local channel slots and observed channel activity.
- `Ch 0` can be the active primary even when its channel name is blank.
- Leaving `PSK` blank in the editor keeps the current key.
- `MQTT Up` / `MQTT Down` are bridge toggles, not LoRa TX/RX controls.
- Message channels are encryption groups. They are not RF frequency slots.
- Local slots should stay consecutive (`0..N`). Add the next free slot; disable from the end.
- See: `docs/CHANNELS.md`

## Troubleshooting

Check service status:

```bash
sudo systemctl status meshtastic-dashboard --no-pager
```

Follow logs:

```bash
sudo journalctl -u meshtastic-dashboard -f
```

Verify listener:

```bash
ss -ltnp | grep 8877
```

Verify history DB exists:

```bash
ls -lh /home/j/mesh/mesh_dashboard_history*.sqlite3
```

If UI seems stale after deploy, hard-refresh browser (`Ctrl+Shift+R`).

### Diagnostics Runbook: "Server crashed" vs "Radio disconnected"

When the dashboard appears down, run this sequence on the host (for example `192.168.1.241`) before unplugging hardware:

```bash
# 1) Current/last service health
sudo systemctl status meshtastic-dashboard --no-pager -l
sudo systemctl show meshtastic-dashboard \
  -p ActiveState -p SubState -p NRestarts -p ExecMainCode -p ExecMainStatus \
  -p ExecMainStartTimestamp -p ExecMainExitTimestamp

# 2) Logs in the exact incident window
sudo journalctl -u meshtastic-dashboard \
  --since "YYYY-MM-DD HH:MM:SS" --until "YYYY-MM-DD HH:MM:SS" \
  -o short-iso --no-pager

# 3) Host reboot/kernel-level checks
sudo journalctl --list-boots
sudo journalctl -u meshtastic-dashboard -b -1 -o short-iso --no-pager | tail -n 200
sudo journalctl -k -b -1 -p warning --no-pager | egrep -i "oom|killed process|segfault|panic|watchdog"
last -x | head -n 20

# 4) Verify radio path exists
ls -l /dev/serial/by-id
```

Interpretation:

- If you see `Meshtastic serial port disconnected` followed by repeated `No such file or directory` for `/dev/serial/by-id/...`, the issue is radio/USB path loss (unplug, power reset, cable/hub issue, or port contention), not a Python crash.
- If `ActiveState=active`, `SubState=running`, and `NRestarts` is not increasing, the service itself is healthy.
- If kernel logs show OOM/panic/segfault, investigate host stability and memory pressure.

Quick recovery after radio reconnect:

```bash
sudo systemctl restart meshtastic-dashboard
sudo systemctl status meshtastic-dashboard --no-pager -l
sudo journalctl -u meshtastic-dashboard -f
```

Optional: check for other software holding the serial port:

```bash
sudo lsof /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Incident reference (March 6, 2026):

- Service remained healthy after restart (`ActiveState=active`, `SubState=running`, `NRestarts=0`).
- Logs showed serial disconnect at `2026-03-06T14:52:10-06:00` and repeated missing device path errors until reconnect.
- Device path returned as `/dev/serial/by-id/... -> ../../ttyACM0`, and the dashboard resumed normally.

## Development and Tests

Install dev dependency:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest
```

## Security Notes

- Dashboard HTTP has no authentication by default.
- Do not expose it directly to the public internet.
- Restrict to trusted LAN/VPN segments.
