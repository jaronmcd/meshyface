"""Zork plugin for mesh and local console sessions."""

from __future__ import annotations

import time

from meshdash.plugins import Script

try:
    from .zork_core import ZorkGame
except ImportError:  # pragma: no cover - supports direct runpy-based examples.
    from meshdash.included_plugins.zork.zork_core import ZorkGame


script = Script(id="zork", name="Zork", version="1.0.0")
script.ticker("activity", label="Zork", default_enabled=True)

_PUBLIC_START_TRIGGER = "zork"
_game = ZorkGame()
_request_count = 0
_reply_count = 0
_last_activity_unix = 0


def _publish_activity_ticker(ctx, now_unix: int) -> None:
    sessions = _game.session_summaries(now_unix)
    rows = {
        "Game": "Zork",
        "Sess": f"{len(sessions)} active",
    }
    if sessions:
        active = []
        for session in sessions[:2]:
            peer_id = str(session.get("peer_id") or "")
            peer_label = peer_id[-4:] if peer_id else "peer"
            room = str(session.get("room_name") or session.get("room") or "").strip()
            active.append(f"{peer_label} · {room}" if room else peer_label)
        if len(sessions) > len(active):
            active.append(f"+{len(sessions) - len(active)}")
        rows["Now"] = ", ".join(active)
    rows["Req/Rep"] = f"{_request_count}/{_reply_count}"
    rows["Last"] = (
        time.strftime("%H:%M:%S", time.localtime(_last_activity_unix))
        if _last_activity_unix
        else "none"
    )
    ctx.set_ticker(
        "activity",
        value=f"{len(sessions)} session{'s' if len(sessions) != 1 else ''}",
        rows=rows,
        state="good" if sessions else "neutral",
        detail=(
            f"Zork · {len(sessions)} active · "
            f"{_request_count} requests · {_reply_count} replies"
        ),
    )


@script.on_start
def zork_start(ctx):
    _publish_activity_ticker(ctx, int(time.time()))


def _sync_host_session(ctx, *, active_before: bool, active_after: bool) -> None:
    message = ctx.message
    session = getattr(ctx, "session", None)
    if session is None or not getattr(message, "is_direct", False):
        return
    if active_after:
        session.start()
    elif active_before:
        session.end()


def _run_zork(ctx, *, allow_public_start: bool):
    global _last_activity_unix, _reply_count, _request_count

    message = ctx.message
    text = str(message.text or "").strip()
    if not text:
        return None

    if message.is_broadcast:
        if not allow_public_start or text.casefold() != _PUBLIC_START_TRIGGER:
            return None
        # The old script accepted only an exact public "zork", then converted it
        # into a private game keyed to the sender and replied directly.
        destination_id = message.local_node_id
    elif message.is_direct:
        destination_id = message.destination_id
    else:
        return None

    now_unix = int(time.time())
    active_before = _game.has_active_session(message.sender_id)
    result = _game.try_handle_message(
        text=text,
        from_id=message.sender_id,
        to_id=destination_id,
        local_node_id=message.local_node_id,
        now_unix=now_unix,
        enabled=True,
    )
    if not result.handled:
        return None
    _sync_host_session(
        ctx,
        active_before=active_before,
        active_after=_game.has_active_session(message.sender_id),
    )
    _request_count += 1
    reply = str(result.reply_text or "").strip()
    if reply:
        _reply_count += 1
    _last_activity_unix = now_unix
    _publish_activity_ticker(ctx, now_unix)
    return ctx.reply_long(reply) if reply else None


@script.command("zork")
def zork_command(ctx):
    # A public !zork was not an old-script trigger; public starts remain exact
    # unprefixed "zork" messages. Direct !zork starts or restarts normally.
    return _run_zork(ctx, allow_public_start=False)


@script.session
def zork_session(ctx):
    return _run_zork(ctx, allow_public_start=False)


@script.on_message
def zork_message(ctx):
    # Direct messages are offered to the game so an active peer can use its
    # normal unprefixed verbs. ZorkGame ignores unrelated direct messages.
    return _run_zork(ctx, allow_public_start=True)
