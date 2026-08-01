# Packet City

This example subscribes to every accepted packet with `@script.on_packet`, looks
up the sender's nearest known city, and emits one `packet&city:` entry through
`ctx.debug()`. MeshyFace shows it in the Scripts console and foreground terminal.

While the plugin is enabled, its Script's **Packet City** ticker runs a demo city
leaderboard. Every accepted packet with a known sender location adds a point to
its nearest city, and the ticker continuously displays the top cities. Cities
outside the visible top three are grouped as **Other**, with their names kept in
the ticker tooltip. Packets without a resolvable city are counted as **No city**,
and **Seen** shows the latest packet time. Scores reset when the script worker
restarts, so the example works without configuration in any region.

Enable it with `--plugin-enable packet_city`.
