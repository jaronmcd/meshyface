# Prerequisites And Dependencies

Meshyface is a Python web service. For a persistent dashboard host, use Linux
with systemd; Debian, Ubuntu, and Raspberry Pi OS Bookworm or newer are the
expected paths.

Required host packages for the standalone install:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv
```

Runtime requirements:

- Python `3.11+`
- outbound HTTPS during install for GitHub and PyPI, unless dependencies are
  already mirrored or cached
- a Meshtastic radio reachable over TCP (`--mesh-host` + `--mesh-tcp-port`) or
  USB serial (`--mesh-port`)
- for USB serial, a stable `/dev/serial/by-id/...` path is recommended
- for USB serial under systemd, the service user must have access to the serial
  device; the documented unit uses group `dialout`

Python runtime packages are pinned in `requirements.txt`:

- `meshtastic==2.7.8`
- `pypubsub==4.0.7`
- `protobuf==7.34.1`

Install them with:

```bash
python -m pip install -r requirements.txt
```

Development and test dependencies live in `requirements-dev.txt`:

```bash
python -m pip install -r requirements-dev.txt
```

Browser access to `https://tile.openstreetmap.org/...` is only needed for
online basemaps.

For a fully air-gapped deployment, the vendored Leaflet and particles.js assets
still load locally, and the map uses the bundled offline atlas when online tile
servers are unavailable.
