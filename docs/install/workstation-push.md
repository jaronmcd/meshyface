# Workstation Push Deployment

For public installs, prefer the standalone clone plus systemd flow. The
Settings Software panel expects the running app to be a git checkout when you
want in-app GitHub updates.

`scripts/deploy_meshyface.sh` is a workstation-managed push deploy helper. It
copies the local checkout over SSH, renders a target-specific systemd unit, and
can bootstrap or reset a host. It is useful when:

- the target should not or cannot clone from GitHub directly
- you are pushing local, unreleased changes
- you want a one-command Raspberry Pi or Proxmox bootstrap from your workstation
- you need the reset/uninstall flows built into the helper

It is not a fully offline installer. During `--bootstrap` it still uses the
target host's package manager and `pip` unless those dependencies are already
provisioned. A deploy-helper-managed app directory is also a copied payload, not
a git checkout, so update those hosts by rerunning the helper instead of using
the in-app git updater.

## Push Bootstrap/Deploy From Your Workstation

From this repo:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --bootstrap \
  --mesh-host meshtastic-radio.local \
  --mesh-port 4403 \
  --clean-app-dir
```

This installs the runtime, deploys app files from your local checkout, writes
`dashboard.env`, and restarts the service. The helper records the local git
commit as the deployed revision. Add `--pr-number <number>` for an unmerged PR
preview. Without an explicit number, the helper clears stale preview metadata
unless the checked-out merge or squash commit identifies its PR automatically.

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

## Update Loop

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --mesh-host meshtastic-radio.local \
  --mesh-port 4403 \
  --clean-app-dir
```

## Deploy A Local Map Pack

Build a mesh-sized zip on the workstation, then copy and install it with the
same deploy helper:

```bash
./scripts/deploy_meshyface.sh \
  --target pi@meshyface.local \
  --map-pack-zip mymesh.zip
```

The uploaded staging zip is removed after a successful installation. See
[Offline And Custom Map Data](offline-map-packs.md) for the build command.

## Full Reset + Redeploy

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

## Full Uninstall + Hard Reboot

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

## Raspberry Pi Target

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
