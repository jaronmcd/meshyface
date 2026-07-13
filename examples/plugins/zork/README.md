# Zork compatibility plugin

This copyable plugin exports a Script that wraps Meshyface's existing `ZorkGame`
engine and preserves
the former mesh Zork script's message behavior:

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
the script or dashboard restarts. The standalone local Console game remains a
separate feature controlled by `--games-enable`.

This repository location is an example, not an automatically installed plugin.
For the standard systemd deployment, copy the package to the persistent plugin
directory before enabling it:

```bash
scp -r examples/plugins/zork j@192.168.1.67:/home/j/mesh/plugins/
MESH_DASH_DEPLOY_PLUGIN_ENABLE=zork ./scripts/deploy_meshyface.sh --target j@192.168.1.67 --plugins-enable
```

Alternatively, copy it, restart Meshyface once so it is discovered, and enable
**Zork** from **Apps → Scripts**. The plugin runtime requires `--plugins-enable`; it
does not require `--games-enable`.
