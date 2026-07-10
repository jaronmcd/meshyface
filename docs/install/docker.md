# Docker

The Docker image runs the same `mesh_dashboard.py` entrypoint as the standalone
install. It stores SQLite history, theme settings, and installed map packs under
`/data` by default, so mount a volume there if you want state to survive
container replacement. The image includes the map-pack build and install tools
shown by the dashboard.

To install a locally built pack into a running container:

```bash
docker cp mymesh.zip <container>:/data/mymesh.zip
docker exec <container> python scripts/install_map_pack.py --zip /data/mymesh.zip --yes
```

## Build Image

```bash
docker build \
  --build-arg MESH_DASH_GIT_COMMIT="$(git rev-parse --short=12 HEAD)" \
  -t meshyface:local .
```

For an unmerged PR preview, also pass
`--build-arg MESH_DASH_PR_NUMBER=<number>`. Compose accepts the same
`MESH_DASH_GIT_COMMIT` and `MESH_DASH_PR_NUMBER` environment variables.

## Run With Wi-Fi/TCP Radio

```bash
docker run --rm -it \
  -p 8877:8877 \
  -v meshyface-data:/data \
  -e MESH_GATEWAY_HOST=meshtastic-radio.local \
  -e MESH_GATEWAY_PORT=4403 \
  meshyface:local
```

Then open `http://127.0.0.1:8877`.

## Run With USB Serial Radio

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

## Docker Compose

For a TCP radio:

```bash
MESH_DASH_GIT_COMMIT="$(git rev-parse --short=12 HEAD)" \
  MESH_GATEWAY_HOST=meshtastic-radio.local \
  docker compose --profile tcp up -d --build
```

For a USB serial radio:

```bash
MESH_DASH_GIT_COMMIT="$(git rev-parse --short=12 HEAD)" \
  MESH_DASH_MESH_PORT=/dev/ttyACM0 \
  docker compose --profile serial up -d --build
```

The Compose file publishes `8877`, uses the named volume `meshyface-data`, and
keeps optional BBS, games, and file-transfer features disabled unless you enable
their documented environment variables.
