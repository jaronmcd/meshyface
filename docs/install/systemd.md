# Recommended Systemd Service

This is the preferred public GitHub install path for persistent hosts. It keeps
the dashboard as a normal git checkout, so the Software panel in Settings can
check GitHub branches and apply git-based updates. If you want to push a local
checkout from a workstation over SSH instead, use
[Workstation Push Deployment](workstation-push.md).

The `/opt/meshyface` path is a system-wide install convention for the included
service unit. It is not special to the app, but the commands below and
`meshtastic-dashboard.service` assume this layout:

- repo clone: `/opt/meshyface`
- virtualenv: `/opt/meshyface/.venv`
- environment file: `/etc/meshyface/dashboard.env`
- writable app data: `/var/lib/meshyface`
- service user/group: `meshyface` / `dialout`

If you clone somewhere else, update every `/opt/meshyface` path in the service
unit and commands. For the copy/paste install below, clone directly into
`/opt/meshyface`; do not also create a separate `~/meshyface` checkout unless
you want a personal test copy.

On a Debian, Ubuntu, or Raspberry Pi OS host:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv
sudo useradd --system --create-home --groups dialout meshyface || true
sudo install -d -o meshyface -g dialout /opt/meshyface
sudo -u meshyface git clone https://github.com/jaronmcd/meshyface.git /opt/meshyface
sudo -u meshyface python3 -m venv /opt/meshyface/.venv
sudo -u meshyface /opt/meshyface/.venv/bin/python -m pip install --upgrade pip
sudo -u meshyface /opt/meshyface/.venv/bin/python -m pip install -r /opt/meshyface/requirements.txt
sudo install -d -o root -g dialout -m 0750 /etc/meshyface
sudo install -d -o meshyface -g dialout -m 0750 /var/lib/meshyface
```

For a Wi-Fi/TCP radio, create `/etc/meshyface/dashboard.env` with:

```bash
sudo tee /etc/meshyface/dashboard.env >/dev/null <<'EOF'
MESH_GATEWAY_HOST=192.168.1.42
MESH_GATEWAY_PORT=4403
MESH_DASH_HISTORY_DB=/var/lib/meshyface/mesh_dashboard_history.sqlite3
MESH_DASH_THEME_SETTINGS_FILE=/var/lib/meshyface/mesh_dashboard_theme_settings.json
MESH_DASHBOARD_MAP_PACKS_DIR=/var/lib/meshyface/map_packs
PYTHONUNBUFFERED=1
EOF
sudo chown root:dialout /etc/meshyface/dashboard.env
sudo chmod 0640 /etc/meshyface/dashboard.env
```

For a USB serial radio, use this `dashboard.env` instead:

```bash
sudo tee /etc/meshyface/dashboard.env >/dev/null <<'EOF'
MESH_DASH_MESH_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
MESH_DASH_HISTORY_DB=/var/lib/meshyface/mesh_dashboard_history.sqlite3
MESH_DASH_THEME_SETTINGS_FILE=/var/lib/meshyface/mesh_dashboard_theme_settings.json
MESH_DASHBOARD_MAP_PACKS_DIR=/var/lib/meshyface/map_packs
PYTHONUNBUFFERED=1
EOF
sudo chown root:dialout /etc/meshyface/dashboard.env
sudo chmod 0640 /etc/meshyface/dashboard.env
```

Then install and start the service:

```bash
cd /opt/meshyface
sudo install -m 0644 meshtastic-dashboard.service /etc/systemd/system/meshtastic-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-dashboard
sudo systemctl status meshtastic-dashboard --no-pager -l
```

After pulling updates:

```bash
cd /opt/meshyface
sudo -u meshyface git pull --ff-only
sudo -u meshyface /opt/meshyface/.venv/bin/python -m pip install -r requirements.txt
sudo systemctl restart meshtastic-dashboard
```

To uninstall this systemd layout and remove its managed data:

```bash
sudo systemctl disable --now meshtastic-dashboard.service 2>/dev/null || true
sudo systemctl stop meshtastic-dashboard.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/meshtastic-dashboard.service
sudo rm -f /etc/systemd/system/multi-user.target.wants/meshtastic-dashboard.service
sudo systemctl daemon-reload
sudo systemctl reset-failed meshtastic-dashboard.service 2>/dev/null || true

sudo rm -rf /opt/meshyface
sudo rm -rf /etc/meshyface
sudo rm -rf /var/lib/meshyface

if getent passwd meshyface >/dev/null; then
  sudo userdel -r meshyface 2>/dev/null || sudo userdel meshyface
fi
sudo rm -rf /home/meshyface
```

If you also made a separate test checkout under your login user's home, remove
that checkout separately, for example `rm -rf ~/meshyface`.
