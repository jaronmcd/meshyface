Mini-games for `MeshResponseBot` live here.

The current bot is wired to `meshdash/games/zork/`.

If you want to make your own game:

1. Copy the `zork/` folder.
2. Change the room map and rules there.
3. Point `meshdash/bot_responder.py` at your new game class.

The goal is to keep the game code separate from the transport, logging, and bot settings code.
