This folder contains the current peer-to-peer text adventure used by the bot.

Files:

- `world.py`: room layout and item placement.
- `engine.py`: command parsing, session state, and game rules.
- `port_tools/extract_upstream_rooms.py`: helper that extracts room data from the original MDL source.
- `upstream_1977/extracted_rooms.json`: generated structured room data from the upstream source.
- `upstream_1977/zork-master/`: original 1977 MIT Zork MDL source and archival files.

Important:

- The current Python bot app is still a simplified playable example.
- The files under `upstream_1977/zork-master/` are reference source, not directly executable by Meshyface.
- A true "full game" port means translating the MDL game logic into this Python bot-app structure.
- The live game now starts in the classic `West of House` opening and uses the extracted upstream room graph plus parsed upstream object data.
- The current live port supports classic navigation, inventory, reading/examining, mailbox/window/trap-door/grating interactions, lamp/torch/candle lighting, the early troll-room combat path, rope-and-dome traversal, the riddle-room door word, cyclops bypass via the classic magic word, rainbow toggling with the stick, real board/launch/land/disembark river travel with the inflatable boat, the buoy/emerald pickup, dam control-room button/bolt logic with low-tide reservoir crossings, the bell-book-candles exorcism path into Hades, glacier melting with the torch, mirror rubbing/breaking, the machine-room coal-to-diamond path, the safe/brick/fuse treasure path, generic container stashing (including the trophy case and mailbox), bulk `take/drop/put` handling for `all` and `valuables`, bat-room garlic behavior with live bat drops, gas-room open-flame deaths, shovel-driven digging at the beach and guano cave, a live thief encounter plus simplified roaming/stalking theft, the classic sharp-stick boat puncture gag plus putty repair for the damaged boat, sword glow warnings near villains, playable balloon travel in the volcano via the basket/receptacle/wire/hooks cluster, the live volcano-gnome west-door route (`give zorkmid to gnome` / `throw zorkmid at gnome`), the carousel/low-room magnetic scramble with the CMACH round/square/triangular button cluster, a live robot/sphere/high-voltage path with actor-style `robot ...` commands, the Alice tea-room size/cake/flask branch (`eat cake`, `read <cake> through flask`, explosive orange cake, evaporating red-cake pool trick, fatal flask vapors), the live mine dumbwaiter/shaft basket route (`raise basket`, `lower basket`, cargo transfer through the empty-handed shaft choke point), maintenance-room leak plugging with putty, the end-of-rainbow return path back onto a solid rainbow plus the fatal barrel `launch`/`geronimo` gag, a more faithful Land of the Living Dead branch (`look` in `LLD2`, `attack ghost`, `take bodies`, `burn bodies`, and re-`exorcise` behavior are now much closer to upstream), and a live `score`/`quit` progress summary. The magic well/bucket route is now live too: saying `well` at the top or bottom of the well summons the bucket, `board bucket` lets you ride it, and saying `well` while aboard carries you between the top and bottom of the shaft. The safe/volcano event chain is less fake now too: `light fuse` burns for a couple of turns before detonating, the safe room can later collapse into rubble, the high ledge can collapse belatedly, and the volcano gnome now grows nervous and leaves if you waste his time.

Useful Alice-branch commands now include `eat cake`, `eat blue cake`, `throw red cake at pool`, `read red cake through flask`, the ill-advised `open flask`, and the useful `well` / `board bucket` sequence for the Pearl Room route. Useful volcano commands now include `give zorkmid to gnome`, `throw zorkmid at gnome`, `light fuse` in the safe if you enjoy delayed geological consequences, and the very stupid `launch` or `geronimo` while inside the barrel at the falls.

If you need to regenerate the extracted room data:

```bash
python -m meshdash.games.zork.port_tools.extract_upstream_rooms
```

To make your own game, the fastest path is:

1. Duplicate this folder.
2. Rename the class and `SPEC` metadata in `engine.py`.
3. Rewrite `world.py` to match your map.
4. Adjust `engine.py` for any new verbs, puzzles, or win conditions.
5. Add a plugin module under `meshdash/bot_plugins/` that returns your app from
   `build_bot_apps()` (or exports `BOT_APPS`).
6. (Optional) Load plugin modules from outside the package with
   `MESH_DASH_BOT_PLUGIN_MODULES`.
7. For command-style bots, prefer `meshdash.bot_sdk.CommandApp`.

The bot only provides message routing, settings, and request logging. The app logic stays here.

For the built-in Zork example specifically, the porting path is:

1. Use `upstream_1977/zork-master/` as the authoritative game reference.
2. Start from `upstream_1977/extracted_rooms.json` for the room graph.
3. Extend the remaining late-game conditionals, object routines, fuller thief/scoring logic, broader robot actor behavior, broader volcano timing details, and deeper death handling.
4. Keep adding puzzle-specific behavior while preserving the data-driven room/object loader and condition/action registries.
5. Grow regression tests with every new mechanic so the port does not drift.
