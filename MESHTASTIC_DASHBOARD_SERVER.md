# Meshtastic Dashboard as a Server Service

This runs `mesh_dashboard.py` as a persistent systemd service on your Debian VM.

Recommended source for mesh data:

- Home Assistant Meshtastic TCP proxy at `192.168.1.109:4403`

## 1) Copy app files to the VM

From your laptop (`j-dbox`):

```bash
scp /home/j/mesh_py/mesh_dashboard.py j@192.168.1.241:/home/j/mesh/app/
scp /home/j/mesh_py/mesh_connection.py j@192.168.1.241:/home/j/mesh/app/
scp /home/j/mesh_py/meshtastic-dashboard.service j@192.168.1.241:/home/j/
```

## 2) Create dashboard env file on VM

```bash
cat > /home/j/mesh/config/dashboard.env <<'EOF'
MESH_HOST=192.168.1.109
MESH_PORT=4403
DASH_HOST=0.0.0.0
DASH_PORT=8877
REFRESH_MS=3000
EOF
```

## 3) Create virtualenv and install dependencies on VM

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv /home/j/mesh/.venv
/home/j/mesh/.venv/bin/pip install --upgrade pip
/home/j/mesh/.venv/bin/pip install meshtastic pypubsub protobuf
```

## 4) Install and start service

```bash
sudo cp /home/j/meshtastic-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meshtastic-dashboard
sudo systemctl status meshtastic-dashboard --no-pager
```

## 5) Verify and access

```bash
journalctl -u meshtastic-dashboard -f
```

Open:

- `http://192.168.1.241:8877`

## Notes

- If you later change HA proxy port, update `MESH_PORT` in `/home/j/mesh/config/dashboard.env`.
- To show raw secrets in dashboard output, add `--show-secrets` to `ExecStart` in the systemd service and restart.
