# Proxmox Runtime Topology

You have two common deployment models:

1. Proxmox VM/LXC + radio reachable over LAN (TCP) - simplest and most stable
2. Proxmox VM/LXC + USB radio passthrough (serial) - works, but needs device
   passthrough

## Recommended: Proxmox With TCP Radio

If your radio is on Wi-Fi/Ethernet and exposes TCP (usually `4403`), run the
dashboard in a VM or container and connect over network. Use the
[recommended systemd service](systemd.md) or [Docker install](docker.md) inside
that VM/container.
