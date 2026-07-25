# Zork compatibility plugin

This copyable plugin exports a Script and owns its `ZorkGame` engine inside the
plugin package. It preserves the former mesh Zork script's message behavior:

- an exact public `zork` starts a private game and sends the reply directly;
- direct `zork`, `!zork`, `#zork`, or `restart` starts or restarts a game;
- later direct messages are treated as game commands for that peer;
- unrelated public traffic is ignored; and
- replies use the Scripts runtime's byte-safe, paced long-reply transport.

When the plugin is enabled, its Script declares a **Zork** summary ticker mirroring
the former script ticker: active sessions, current peers/rooms, request/reply
counts, and last activity. Disabling the script hides the ticker automatically.

The engine keeps up to 128 peer sessions and expires idle games after 45
minutes, as the old script did. Sessions live in the script worker and reset when
the script or dashboard restarts. When the plugin is enabled, its manifest
command also appears in the local browser Console. Console play uses the same
command and session handlers as mesh play, but replies are returned to the
browser instead of sent over the radio.

This reference plugin is bundled with Meshyface and included in standard
systemd and container deployments. Enable Zork during a systemd deployment with:

```bash
MESH_DASH_DEPLOY_PLUGIN_ENABLE=zork ./scripts/deploy_meshyface.sh --target j@192.168.1.67
```

No plugin copy step is required. Alternatively, enable **Zork** from
**Apps → Scripts**. The plugin runtime does not require `--games-enable`.
