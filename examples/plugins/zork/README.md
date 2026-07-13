# Zork compatibility script

This copyable script wraps Meshyface's existing `ZorkGame` engine and preserves
the former mesh Zork bot's message behavior:

- an exact public `zork` starts a private game and sends the reply directly;
- direct `zork`, `!zork`, `#zork`, or `restart` starts or restarts a game;
- later direct messages are treated as game commands for that peer;
- unrelated public traffic is ignored; and
- replies use the Scripts runtime's byte-safe, paced long-reply transport.

The engine keeps up to 128 peer sessions and expires idle games after 45
minutes, as the old bot did. Sessions live in the script worker and reset when
the script or dashboard restarts. The standalone local Console game remains a
separate feature controlled by `--games-enable`.

This repository location is an example, not an automatically installed script.
For the standard systemd deployment, copy the package to the persistent plugin
directory before enabling it:

```bash
scp -R examples/plugins/zork \
  j@192.168.1.67:/home/j/mesh/plugins/

MESH_DASH_DEPLOY_BOT_ENABLE=zork \
./scripts/deploy_meshyface.sh \
  --target j@192.168.1.67 \
  --bots-enable
```

Alternatively, copy it, restart Meshyface once so it is discovered, and enable
**Zork** from **Apps → Scripts**. The mesh script requires `--bots-enable`; it
does not require `--games-enable`.
