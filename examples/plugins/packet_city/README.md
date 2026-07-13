# Packet & City Debug

This example subscribes to every accepted packet with `@bot.on_packet`, looks
up the sender's nearest known city, and prints one `packet&city:` JSON line to
the dashboard's foreground terminal.

Enable it with `--bots-enable --bots-directory examples/plugins --bot-enable packet_city`.
