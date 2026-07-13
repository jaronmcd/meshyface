# Packet & City Debug

This example subscribes to every accepted packet with `@bot.on_packet`, looks
up the sender's nearest known city, and emits one `packet&city:` entry through
`ctx.debug()`. MeshyFace shows it in the Scripts console and foreground terminal.

Enable it with `--bots-enable --bots-directory examples/plugins --bot-enable packet_city`.
