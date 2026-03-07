This folder contains the current peer-to-peer text adventure used by the bot.

Files:

- `world.py`: room layout and item placement.
- `engine.py`: command parsing, session state, and game rules.

To make your own game, the fastest path is:

1. Duplicate this folder.
2. Rewrite `world.py` to match your map.
3. Adjust `engine.py` for any new verbs, puzzles, or win conditions.
4. Update `meshdash/bot_responder.py` to import your new game class.

The bot only provides message routing, settings, and request logging. The game logic stays here.
