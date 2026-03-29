Mini-games for `MeshResponseBot` live here.

The current bot app example lives in `meshdash/games/zork/`.
That folder now also includes `upstream_1977/zork-master/`, which is the archived MIT Zork source used as the reference for a future fuller port.

If you want to make your own game:

1. Copy the `zork/` folder.
2. Rename the class/command metadata in your copied `engine.py`.
3. Change the room map and rules there.
4. Add a plugin module under `meshdash/bot_plugins/` that returns your app from
   `build_bot_apps()` (or exports `BOT_APPS`).
5. (Optional) Load plugin modules from outside the package with
   `MESH_DASH_BOT_PLUGIN_MODULES`.
6. For command-style bots, prefer the SDK helper `meshdash.bot_sdk.CommandApp`.

The goal is to keep the app code separate from the transport, logging, and bot settings code.
