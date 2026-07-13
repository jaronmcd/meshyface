"""Compatibility wrapper for the former built-in Meshyface Zork bot."""

from __future__ import annotations

import time

from meshdash.bots import Bot
from meshdash.games.zork import ZorkGame


bot = Bot(id="zork", name="Zork", version="1.0.0")

_PUBLIC_START_TRIGGER = "zork"
_game = ZorkGame()


def _run_zork(ctx, *, allow_public_start: bool):
    message = ctx.message
    text = str(message.text or "").strip()
    if not text:
        return None

    if message.is_broadcast:
        if not allow_public_start or text.casefold() != _PUBLIC_START_TRIGGER:
            return None
        # The old bot accepted only an exact public "zork", then converted it
        # into a private game keyed to the sender and replied directly.
        destination_id = message.local_node_id
    elif message.is_direct:
        destination_id = message.destination_id
    else:
        return None

    result = _game.try_handle_message(
        text=text,
        from_id=message.sender_id,
        to_id=destination_id,
        local_node_id=message.local_node_id,
        now_unix=int(time.time()),
        enabled=True,
    )
    if not result.handled:
        return None
    reply = str(result.reply_text or "").strip()
    return ctx.reply_long(reply) if reply else None


@bot.command("zork")
def zork_command(ctx):
    # A public !zork was not an old-bot trigger; public starts remain exact
    # unprefixed "zork" messages. Direct !zork starts or restarts normally.
    return _run_zork(ctx, allow_public_start=False)


@bot.on_message
def zork_message(ctx):
    # Direct messages are offered to the game so an active peer can use its
    # normal unprefixed verbs. ZorkGame ignores unrelated direct messages.
    return _run_zork(ctx, allow_public_start=True)
