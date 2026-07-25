from __future__ import annotations

import runpy
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from meshdash.plugins import (
    Script,
    MessageEvent,
    ReplyAction,
    parse_manifest,
    validate_script_against_manifest,
)
from meshdash.plugin_runtime import PluginRuntime, PluginRuntimeConfig
from meshdash.plugin_state import PluginStateStore


REPO_ROOT = Path(__file__).resolve().parents[1]
ZORK_EXAMPLE = REPO_ROOT / "meshdash" / "included_plugins" / "zork"


def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true before timeout")


def _event(
    text: str,
    *,
    sender_id: str = "!00000001",
    destination_id: str = "!00000002",
    packet_id: int = 10,
) -> MessageEvent:
    broadcast = destination_id == "^all"
    return MessageEvent(
        text=text,
        sender_id=sender_id,
        destination_id=destination_id,
        local_node_id="!00000002",
        channel_index=3,
        is_direct=not broadcast,
        is_broadcast=broadcast,
        packet_id=packet_id,
        reply_packet_id=None,
        received_at=time.time(),
    )


def _context(
    text: str,
    *,
    sender_id: str = "!00000001",
    direct: bool = True,
    broadcast: bool = False,
):
    replies: list[str] = []
    tickers: list[dict[str, object]] = []

    def _reply_long(value: str) -> ReplyAction:
        replies.append(value)
        return ReplyAction(value, long=True)

    def _set_ticker(ticker_id: str, **kwargs: object) -> None:
        tickers.append({"id": ticker_id, **kwargs})

    return SimpleNamespace(
        message=SimpleNamespace(
            text=text,
            sender_id=sender_id,
            destination_id="^all" if broadcast else "!00000002",
            local_node_id="!00000002",
            is_direct=direct,
            is_broadcast=broadcast,
        ),
        reply_long=_reply_long,
        set_ticker=_set_ticker,
        replies=replies,
        tickers=tickers,
    )


def test_zork_example_matches_manifest_and_preserves_direct_gameplay() -> None:
    manifest = parse_manifest(ZORK_EXAMPLE / "plugin.toml")
    namespace = runpy.run_path(str(manifest.entrypoint_path))
    script = namespace[manifest.entrypoint_object]

    assert isinstance(script, Script)
    assert validate_script_against_manifest(manifest, script) is script
    assert manifest.id == "zork"
    assert manifest.commands == ("zork",)
    assert manifest.default_enabled is False
    assert tuple(script.tickers) == ("activity",)

    start_context = _context("zork")
    start = script.message_handler(start_context)
    assert isinstance(start, ReplyAction)
    assert start.long is True
    assert "zork: session started" in start.text
    assert "Type 'help' for the command set." in start.text
    assert start_context.tickers[-1]["id"] == "activity"
    assert start_context.tickers[-1]["state"] == "good"
    assert start_context.tickers[-1]["rows"]["Game"] == "Zork"
    assert start_context.tickers[-1]["rows"]["Sess"] == "1 active"

    look = script.message_handler(_context("look"))
    assert isinstance(look, ReplyAction)
    assert "West of House" in look.text

    quit_reply = script.message_handler(_context("quit"))
    assert isinstance(quit_reply, ReplyAction)
    assert "zork: session ended" in quit_reply.text
    assert script.message_handler(_context("look")) is None


def test_zork_example_keeps_public_trigger_exact_and_replies_privately() -> None:
    manifest = parse_manifest(ZORK_EXAMPLE / "plugin.toml")
    namespace = runpy.run_path(str(manifest.entrypoint_path))
    script = namespace[manifest.entrypoint_object]

    unrelated = _context(
        "I am playing zork",
        sender_id="!00000003",
        direct=False,
        broadcast=True,
    )
    assert script.message_handler(unrelated) is None
    assert unrelated.replies == []

    public_start = _context(
        "ZoRk",
        sender_id="!00000003",
        direct=False,
        broadcast=True,
    )
    start = script.message_handler(public_start)
    assert isinstance(start, ReplyAction)
    assert "zork: session started" in start.text

    direct_follow_up = _context("look", sender_id="!00000003")
    look = script.message_handler(direct_follow_up)
    assert isinstance(look, ReplyAction)
    assert "West of House" in look.text

    public_prefixed = _context(
        "!zork",
        sender_id="!00000004",
        direct=False,
        broadcast=True,
    )
    assert script.commands["zork"](public_prefixed) is None

    direct_prefixed = _context("!zork", sender_id="!00000004")
    prefixed_start = script.commands["zork"](direct_prefixed)
    assert isinstance(prefixed_start, ReplyAction)
    assert "zork: session started" in prefixed_start.text


def test_zork_example_runs_in_spawned_worker_and_routes_private_replies(tmp_path) -> None:
    manifest = parse_manifest(ZORK_EXAMPLE / "plugin.toml")
    store = PluginStateStore(str(tmp_path / "plugin-state.sqlite3"))
    sends: list[dict[str, object]] = []
    sends_lock = threading.Lock()

    def _send(**kwargs: object) -> dict[str, object]:
        with sends_lock:
            sends.append(dict(kwargs))
            return {"message_id": 1000 + len(sends)}

    def _sent_text(destination: str) -> str:
        with sends_lock:
            return " ".join(
                str(row.get("text") or "")
                for row in sends
                if row.get("destination") == destination
            )

    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=_send,
        get_delivery_state_fn=lambda _message_id: {"delivery_state": "acked"},
        config=PluginRuntimeConfig(
            handler_timeout_seconds=2.0,
            long_reply_pace_seconds=0,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("zork")) is True
        _wait_until(lambda: "command set" in _sent_text("!00000001"))
        assert "zork: session started" in _sent_text("!00000001")
        _wait_until(lambda: runtime.status()["tickers"][0]["state"] == "good")  # type: ignore[index]
        ticker = runtime.status()["tickers"][0]  # type: ignore[index]
        assert ticker["id"] == "script:zork:activity"
        assert ticker["rows"][0] == {"key": "Game", "value": "Zork"}
        assert ticker["rows"][1] == {"key": "Sess", "value": "1 active"}
        with sends_lock:
            first_peer_sends = [
                dict(row) for row in sends if row.get("destination") == "!00000001"
            ]
        first_reply_segments = [
            str(row.get("text") or "") for row in first_peer_sends
        ]
        assert len(first_reply_segments) > 1
        assert all(
            segment.startswith(f"[{index}/{len(first_reply_segments)}] ")
            for index, segment in enumerate(first_reply_segments, start=1)
        )
        assert first_peer_sends[0]["reply_id"] == 10
        assert all(row["retry_unacked"] is False for row in first_peer_sends)
        assert all(row["channel_index"] == 3 for row in first_peer_sends)

        assert runtime.try_enqueue(_event("look", packet_id=11)) is True
        _wait_until(lambda: _sent_text("!00000001").count("West of House") >= 2)

        assert runtime.try_enqueue(
            _event(
                "zork",
                sender_id="!00000003",
                destination_id="^all",
                packet_id=12,
            )
        ) is True
        _wait_until(lambda: "zork: session started" in _sent_text("!00000003"))
        assert "command set" in _sent_text("!00000003")
        assert runtime.status()["plugins"]["zork"]["on_message"] is True  # type: ignore[index]
    finally:
        runtime.close()
        store.close()


def test_zork_example_documents_install_and_runtime_boundaries() -> None:
    readme = (ZORK_EXAMPLE / "README.md").read_text(encoding="utf-8")

    for token in (
        "exact public `zork`",
        "bundled with Meshyface",
        "MESH_DASH_DEPLOY_PLUGIN_ENABLE=zork",
        "No plugin copy step is required",
        "--plugins-enable",
        "does not require `--games-enable`",
    ):
        assert token in readme
