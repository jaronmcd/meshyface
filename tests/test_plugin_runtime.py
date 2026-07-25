import os
import threading
import time
from collections import deque
from pathlib import Path

import pytest

from meshdash.file_transfer_protocol import (
    FILE_TRANSFER_CHUNK_BYTES,
    FILE_TRANSFER_MAX_WIRE_BYTES,
)
from meshdash.plugins import (
    AcceptFileOfferAction,
    MessageEvent,
    ReplyAction,
    SendFileAction,
    SendTextAction,
    parse_manifest,
)
from meshdash.plugin_runtime import (
    PluginRuntime,
    PluginRuntimeConfig,
    _QueuedAction,
    _QueuedActionBatch,
    _numbered_utf8_segments,
    _terminal_safe_text,
    _utf8_segments,
)
from meshdash.plugin_state import PluginStateStore


def _write_plugin(
    root: Path,
    plugin_id: str,
    *,
    commands: tuple[str, ...],
    source: str,
):
    directory = root / plugin_id
    directory.mkdir()
    command_toml = ", ".join(f'"{command}"' for command in commands)
    (directory / "plugin.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                f'id = "{plugin_id}"',
                f'name = "{plugin_id.title()}"',
                'version = "1.0.0"',
                'entrypoint = "script.py:script"',
                f"commands = [{command_toml}]",
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (directory / "script.py").write_text(source, encoding="utf-8")
    return parse_manifest(directory / "plugin.toml")


def _event(
    text: str,
    *,
    packet_id: int = 10,
    packet: dict[str, object] | None = None,
    portnum: str | None = None,
    channel_index: int = 0,
    sender_id: str = "!00000001",
) -> MessageEvent:
    return MessageEvent(
        text=text,
        sender_id=sender_id,
        destination_id="!00000002",
        local_node_id="!00000002",
        channel_index=channel_index,
        is_direct=True,
        is_broadcast=False,
        packet_id=packet_id,
        reply_packet_id=None,
        received_at=time.time(),
        packet=packet,
        portnum=portnum if portnum is not None else ("POSITION_APP" if packet else ""),
    )


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true before timeout")


def test_worker_import_handler_state_session_and_reply_are_isolated(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "example",
        commands=("hello",),
        source="""
import os
from meshdash.plugins import Script

script = Script(id="example", name="Example", version="1.0.0")

@script.command("hello")
def hello(ctx):
    ctx.state["worker_pid"] = os.getpid()
    ctx.peer_state["count"] = int(ctx.peer_state.get("count", 0)) + 1
    ctx.session.start()
    return ctx.reply("hello from worker")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    send_lock = threading.Lock()

    def _send(**kwargs: object) -> None:
        with send_lock:
            sends.append(dict(kwargs))

    runtime = PluginRuntime(manifests=[manifest], state_store=store, send_chat_fn=_send)
    try:
        assert runtime.try_enqueue(_event("!hello")) is True
        _wait_until(lambda: bool(sends))
        snapshot = store.snapshot("example", "!00000001")
        assert snapshot.state["worker_pid"] != os.getpid()
        assert snapshot.peer_state == {"count": 1}
        assert store.active_session("!00000002", "!00000001") == "example"
        assert sends[0]["text"] == "hello from worker"
        assert sends[0]["reply_id"] == 10
        status = runtime.status()
        assert status["status"] == "running"
        assert status["worker_ready"] is True
        assert status["plugins"]["example"]["runtime_status"] == "running"  # type: ignore[index]

        assert runtime.try_enqueue(_event("!quit", packet_id=11)) is True
        _wait_until(lambda: len(sends) == 2)
        assert sends[1]["text"] == "Session ended."
        assert store.active_session("!00000002", "!00000001") is None
    finally:
        runtime.close()
        store.close()
    assert runtime.status()["worker_alive"] is False
    assert runtime.status()["worker_ready"] is False
    assert runtime.status()["status"] == "stopped"


def test_console_command_invokes_plugin_handlers_without_radio_sends(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "console",
        commands=("hello",),
        source="""
from meshdash.plugins import Script

script = Script(id="console", name="Console", version="1.0.0")

@script.command("hello")
def hello(ctx):
    ctx.peer_state["command_text"] = ctx.message.text
    ctx.session.start()
    return ctx.reply(f"command:{ctx.message.text}")

@script.session
def session(ctx):
    ctx.peer_state["session_text"] = ctx.message.text
    if ctx.message.text == "done":
        ctx.session.end()
    return ctx.reply(f"session:{ctx.message.text}")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    try:
        start = runtime.run_console_command(
            command="hello",
            text="hello",
            handler="command",
        )
        assert start["ok"] is True
        assert start["reply_text"] == "command:!hello"
        assert start["active_session"] is True
        assert start["session_id"]

        follow_up = runtime.run_console_command(
            command="hello",
            text="look",
            session_id=start["session_id"],
            handler="auto",
        )
        assert follow_up["ok"] is True
        assert follow_up["reply_text"] == "session:look"
        assert follow_up["active_session"] is True

        done = runtime.run_console_command(
            command="hello",
            text="done",
            session_id=start["session_id"],
            handler="auto",
        )
        assert done["ok"] is True
        assert done["reply_text"] == "session:done"
        assert done["active_session"] is False
        assert sends == []
    finally:
        runtime.close()
        store.close()


def test_route_policy_separates_console_and_mesh_access(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "routes",
        commands=("hello",),
        source="""
from meshdash.plugins import Script

script = Script(id="routes", name="Routes", version="1.0.0")

@script.command("hello")
def hello(ctx):
    return ctx.reply(f"nodes={len(ctx.mesh.list_nodes())}")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        node_snapshot_fn=lambda: [{"id": "!00000003"}],
        route_policy={
            "routes": {"mesh_enabled": False, "console_enabled": True}
        },
    )
    try:
        console = runtime.run_console_command(
            command="hello",
            text="hello",
            handler="command",
        )
        assert console["ok"] is True
        assert console["reply_text"] == "nodes=0"
        assert runtime._route_event(_event("!hello")) == ()

        batch = _QueuedActionBatch(
            (_QueuedAction("routes", _event("ignored"), ReplyAction("blocked")),),
            threading.Event(),
        )
        runtime._action_queue.put_nowait(batch)
        batch.ready.set()
        _wait_until(lambda: runtime.status()["action_queue_depth"] == 0)
        assert sends == []

        runtime.update_route_policy(
            {"routes": {"mesh_enabled": True, "console_enabled": False}}
        )
        blocked = runtime.run_console_command(
            command="hello",
            text="hello",
            handler="command",
        )
        assert blocked["ok"] is False
        assert blocked["error"]["code"] == "plugin_console_disabled"  # type: ignore[index]
        assert runtime._route_event(_event("!hello"))[0].plugin_id == "routes"
    finally:
        runtime.close()
        store.close()


def test_peer_state_and_sessions_are_isolated_by_channel(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "scoped",
        commands=("enter",),
        source="""
from meshdash.plugins import Script
script = Script(id="scoped", name="Scoped", version="1.0.0")
@script.command("enter")
def enter(ctx):
    ctx.peer_state["count"] = int(ctx.peer_state.get("count", 0)) + 1
    ctx.session.start()
    return ctx.reply(f"entered {ctx.peer_state['count']}")
@script.session
def session(ctx):
    ctx.peer_state["count"] = int(ctx.peer_state.get("count", 0)) + 1
    return ctx.reply(f"session {ctx.peer_state['count']}")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    try:
        assert runtime.try_enqueue(_event("!enter", packet_id=101, channel_index=0))
        _wait_until(lambda: len(sends) == 1)
        assert runtime.try_enqueue(_event("!enter", packet_id=102, channel_index=1))
        _wait_until(lambda: len(sends) == 2)
        assert store.snapshot("scoped", "!00000001", 0).peer_state == {"count": 1}
        assert store.snapshot("scoped", "!00000001", 1).peer_state == {"count": 1}
        assert store.active_session("!00000002", "!00000001", 0) == "scoped"
        assert store.active_session("!00000002", "!00000001", 1) == "scoped"

        assert runtime.try_enqueue(_event("continue", packet_id=103, channel_index=0))
        _wait_until(lambda: len(sends) == 3)
        assert sends[-1]["text"] == "session 2"
        assert store.snapshot("scoped", "!00000001", 0).peer_state == {"count": 2}
        assert store.snapshot("scoped", "!00000001", 1).peer_state == {"count": 1}

        assert runtime.try_enqueue(_event("!quit", packet_id=104, channel_index=1))
        _wait_until(lambda: len(sends) == 4)
        assert store.active_session("!00000002", "!00000001", 0) == "scoped"
        assert store.active_session("!00000002", "!00000001", 1) is None
    finally:
        runtime.close()
        store.close()


def test_peer_state_quota_rejects_result_without_restarting_worker(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "quota",
        commands=("remember",),
        source="""
from meshdash.plugins import Script
script = Script(id="quota", name="Quota", version="1.0.0")
@script.command("remember")
def remember(ctx):
    ctx.peer_state["seen"] = int(ctx.peer_state.get("seen", 0)) + 1
    return ctx.reply(f"seen {ctx.peer_state['seen']}")
""",
    )
    store = PluginStateStore(
        str(tmp_path / "state.sqlite3"),
        max_peer_state_rows_per_plugin=1,
    )
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    try:
        assert runtime.try_enqueue(_event("!remember", packet_id=111))
        _wait_until(lambda: len(sends) == 1)
        generation = runtime.status()["generation"]

        assert runtime.try_enqueue(
            _event(
                "!remember",
                packet_id=112,
                sender_id="!00000003",
            )
        )
        _wait_until(lambda: "row quota" in str(runtime.status()["last_error"]))
        assert len(sends) == 1
        assert runtime.status()["generation"] == generation
        assert runtime.status()["worker_alive"] is True

        assert runtime.try_enqueue(_event("!remember", packet_id=113))
        _wait_until(lambda: len(sends) == 2)
        assert sends[-1]["text"] == "seen 2"
    finally:
        runtime.close()
        store.close()


def test_packet_handler_runs_inside_worker_with_raw_packet_context(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "packets",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="packets", name="Packets", version="1.0.0")
@script.on_packet
def packet(ctx):
    ctx.peer_state["packet_id"] = ctx.message.packet_id
    ctx.peer_state["portnum"] = ctx.message.portnum
    ctx.peer_state["payload"] = ctx.packet["decoded"]["payload"]
    ctx.debug("packet&city:", {"city": "Test City", "packet_id": ctx.message.packet_id})
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
    )
    try:
        assert runtime.try_enqueue(
            _event("", packet_id=77, packet={"decoded": {"payload": "abcd"}})
        )
        _wait_until(
            lambda: store.snapshot("packets", "!00000001").peer_state
            == {"packet_id": 77, "portnum": "POSITION_APP", "payload": "abcd"}
        )
        _wait_until(lambda: bool(runtime.status()["debug"]))
        assert runtime.status()["debug"][-1]["values"] == [  # type: ignore[index]
            "packet&city:",
            {"city": "Test City", "packet_id": 77},
        ]
        assert runtime.status()["plugins"]["packets"]["on_packet"] is True  # type: ignore[index]
    finally:
        runtime.close()
        store.close()


def test_packet_handler_can_request_host_validated_file_acceptance(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "receiver",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="receiver", name="Receiver", version="1.0.0")
@script.on_packet
def packet(ctx):
    return ctx.accept_file()
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    accepted_packets: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
        accept_file_offer_fn=lambda packet: accepted_packets.append(dict(packet))
        or {"ok": True, "accepted": True},
    )
    packet = {
        "from": 1,
        "to": 2,
        "channel": 0,
        "decoded": {"portnum": 258, "payload": "4d4632"},
    }
    try:
        assert runtime.try_enqueue(_event("", packet=packet, portnum="258"))
        _wait_until(lambda: accepted_packets == [packet])
    finally:
        runtime.close()
        store.close()


def test_quit_never_waits_for_sqlite_on_the_receive_callback(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "sessions",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="sessions", name="Sessions", version="1.0.0")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    store.start_session("!00000002", "!00000001", "sessions")
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    store._lock.acquire()
    lock_held = True
    try:
        started = time.monotonic()
        assert runtime.try_enqueue(_event("!quit", packet_id=12)) is True
        assert time.monotonic() - started < 0.05
        assert sends == []
        store._lock.release()
        lock_held = False
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "Session ended."
        assert store.active_session("!00000002", "!00000001") is None
    finally:
        if lock_held:
            store._lock.release()
        runtime.close()
        store.close()


def test_close_interrupts_an_unreleased_action_batch(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "idle",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="idle", name="Idle", version="1.0.0")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    batch = _QueuedActionBatch(
        (_QueuedAction("host", _event("ignored"), ReplyAction("must not send")),),
        threading.Event(),
    )
    runtime._action_queue.put_nowait(batch)
    _wait_until(lambda: runtime.status()["action_queue_depth"] == 0)
    runtime.close()
    batch.ready.set()
    assert runtime._action_worker.is_alive() is False
    assert sends == []
    store.close()


def test_timeout_restarts_worker_drops_poison_event_and_runs_next_plugin(tmp_path) -> None:
    hung = _write_plugin(
        tmp_path,
        "hung",
        commands=("hang",),
        source="""
from meshdash.plugins import Script
script = Script(id="hung", name="Hung", version="1.0.0")
@script.command("hang")
def hang(ctx):
    while True:
        pass
""",
    )
    healthy = _write_plugin(
        tmp_path,
        "healthy",
        commands=("ok",),
        source="""
from meshdash.plugins import Script
script = Script(id="healthy", name="Healthy", version="1.0.0")
@script.command("ok")
def ok(ctx):
    return ctx.reply("still healthy")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[hung, healthy],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        config=PluginRuntimeConfig(
            handler_timeout_seconds=0.2,
            startup_timeout_seconds=3.0,
            restart_backoff_seconds=0.01,
            long_reply_pace_seconds=0,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("!hang")) is True
        _wait_until(lambda: int(runtime.status()["timeouts"]) >= 1)
        assert runtime.try_enqueue(_event("!ok")) is True
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "still healthy"
        assert int(runtime.status()["generation"]) >= 2
        assert len(sends) == 1
    finally:
        runtime.close()
        store.close()


def test_handler_exception_rolls_back_state_and_does_not_send(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "broken",
        commands=("fail",),
        source="""
from meshdash.plugins import Script
script = Script(id="broken", name="Broken", version="1.0.0")
@script.command("fail")
def fail(ctx):
    ctx.state["should_not_commit"] = True
    raise RuntimeError("boom")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    try:
        runtime.try_enqueue(_event("!fail"))
        _wait_until(lambda: "boom" in str(runtime.status()["last_error"]))
        assert store.snapshot("broken", "!00000001").state == {}
        assert sends == []
    finally:
        runtime.close()
        store.close()


def test_long_reply_segmentation_preserves_unicode_byte_limit() -> None:
    segments = _utf8_segments("alpha 🙂 bravo 🙂 charlie", 11)
    assert " ".join(segments).replace("  ", " ") == "alpha 🙂 bravo 🙂 charlie"
    assert all(len(segment.encode("utf-8")) <= 11 for segment in segments)


def test_long_reply_segments_are_numbered_within_the_radio_byte_limit() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel"

    segments = _numbered_utf8_segments(text, 24)

    assert len(segments) > 1
    assert [
        segment.split("] ", 1)[0] + "]"
        for segment in segments
    ] == [
        f"[{index}/{len(segments)}]"
        for index in range(1, len(segments) + 1)
    ]
    assert all(len(segment.encode("utf-8")) <= 24 for segment in segments)
    assert " ".join(segment.split("] ", 1)[1] for segment in segments) == text


def _long_reply_runtime(
    *,
    send_chat_fn,
    get_delivery_state_fn,
    retry_limit: int = 1,
) -> PluginRuntime:
    runtime = object.__new__(PluginRuntime)
    runtime._send_chat_fn = send_chat_fn
    runtime._get_delivery_state_fn = get_delivery_state_fn
    runtime._closing = threading.Event()
    runtime._config = PluginRuntimeConfig(
        chat_max_bytes=24,
        long_reply_pace_seconds=0,
        long_reply_ack_wait_seconds=0,
        long_reply_ack_poll_seconds=0.05,
        long_reply_retry_limit=retry_limit,
    )
    return runtime


def test_long_reply_waits_for_each_ack_before_sending_the_next_segment() -> None:
    events: list[tuple[str, object]] = []
    acknowledged: set[int] = set()

    def _send(**kwargs: object) -> dict[str, object]:
        message_id = 100 + sum(1 for kind, _value in events if kind == "send")
        events.append(("send", kwargs["text"]))
        acknowledged.add(message_id)
        return {"message_id": message_id}

    def _delivery_state(message_id: object) -> dict[str, object]:
        events.append(("ack", message_id))
        return {
            "delivery_state": (
                "acked" if int(message_id) in acknowledged else "pending"
            )
        }

    runtime = _long_reply_runtime(
        send_chat_fn=_send,
        get_delivery_state_fn=_delivery_state,
    )
    action = ReplyAction(
        "alpha bravo charlie delta echo foxtrot golf hotel",
        long=True,
    )

    runtime._execute_action(_QueuedAction("zork", _event("look"), action))

    sent_segments = [value for kind, value in events if kind == "send"]
    assert len(sent_segments) > 1
    assert events[0][0] == "send"
    assert all(
        events[index][0] == ("send" if index % 2 == 0 else "ack")
        for index in range(len(events))
    )
    assert all(
        str(segment).startswith(f"[{index}/{len(sent_segments)}] ")
        for index, segment in enumerate(sent_segments, start=1)
    )


def test_long_reply_retries_a_segment_before_advancing() -> None:
    sends: list[dict[str, object]] = []
    delivery_states: dict[int, str] = {}

    def _send(**kwargs: object) -> dict[str, object]:
        message_id = 200 + len(sends)
        sends.append(dict(kwargs))
        delivery_states[message_id] = "pending" if message_id == 200 else "acked"
        return {"message_id": message_id}

    runtime = _long_reply_runtime(
        send_chat_fn=_send,
        get_delivery_state_fn=lambda message_id: {
            "delivery_state": delivery_states[int(message_id)]
        },
    )
    action = ReplyAction(
        "alpha bravo charlie delta echo foxtrot golf hotel",
        long=True,
    )

    runtime._execute_action(_QueuedAction("zork", _event("look"), action))

    assert len(sends) > 2
    assert sends[0]["text"] == sends[1]["text"]
    assert sends[0]["retry_of"] is None
    assert sends[1]["retry_of"] == 200
    assert sends[2]["text"] != sends[1]["text"]
    assert all(send["retry_unacked"] is False for send in sends)


def test_long_reply_stops_instead_of_sending_past_an_unacked_segment() -> None:
    sends: list[dict[str, object]] = []

    def _send(**kwargs: object) -> dict[str, object]:
        sends.append(dict(kwargs))
        return {"message_id": 300 + len(sends)}

    runtime = _long_reply_runtime(
        send_chat_fn=_send,
        get_delivery_state_fn=lambda _message_id: {"delivery_state": "pending"},
    )
    action = ReplyAction(
        "alpha bravo charlie delta echo foxtrot golf hotel",
        long=True,
    )

    runtime._execute_action(_QueuedAction("zork", _event("look"), action))

    assert len(sends) == 2
    assert sends[0]["text"] == sends[1]["text"]
    assert sends[1]["retry_of"] == 301


def test_debug_terminal_output_escapes_controls_but_keeps_unicode(capsys) -> None:
    runtime = object.__new__(PluginRuntime)
    runtime._status_lock = threading.RLock()
    runtime._debug_sequence = 0
    runtime._debug_records = deque(maxlen=50)

    runtime._publish_debug(
        "bad\n\x1b]8;;https://example.invalid\x07id",
        [["hello\r\n\x1b[31mred\x9bworld", "snowman ☃"]],
    )

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert "\x1b" not in output
    assert "\x07" not in output
    assert "\x9b" not in output
    assert r"bad\n\x1b]8;;https://example.invalid\x07id" in output
    assert r"hello\r\n\x1b[31mred\x9bworld" in output
    assert "snowman ☃" in output
    assert runtime._debug_records[0]["plugin_id"].startswith("bad\n")
    assert _terminal_safe_text("plain 🙂") == "plain 🙂"


@pytest.mark.parametrize("destination_id", ["!00000000", "!ffffffff", "!FFFFFFFF"])
@pytest.mark.parametrize(
    "action",
    [
        lambda destination_id: SendTextAction(destination_id, "hello"),
        lambda destination_id: SendFileAction(destination_id, "sample.bin"),
    ],
)
def test_plugin_actions_reject_reserved_destinations(
    destination_id,
    action,
) -> None:
    runtime = object.__new__(PluginRuntime)
    runtime._config = PluginRuntimeConfig()

    with pytest.raises(ValueError, match="direct canonical node ID"):
        runtime._validated_actions([action(destination_id).to_dict()])

    assert runtime._validated_actions(
        [action("!00000001").to_dict()]
    ) == (action("!00000001"),)


def test_radio_admission_counts_expanded_frames_and_global_usage(tmp_path) -> None:
    first = _write_plugin(
        tmp_path,
        "first",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="first", name="First", version="1.0.0")
""",
    )
    second = _write_plugin(
        tmp_path,
        "second",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="second", name="Second", version="1.0.0")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[first, second],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
        config=PluginRuntimeConfig(
            chat_max_bytes=4,
            long_reply_retry_limit=0,
            max_actions_per_minute=10,
            max_radio_frames_per_minute=10,
            max_radio_bytes_per_minute=100,
            max_global_radio_frames_per_minute=3,
            max_global_radio_bytes_per_minute=100,
        ),
    )
    try:
        first_action = runtime._queued_external_action(
            "first",
            _event(""),
            ReplyAction("abcdefgh", long=True),
        )
        second_action = runtime._queued_external_action(
            "second",
            _event(""),
            ReplyAction("ijklmnop", long=True),
        )
        assert first_action.radio_frames == 2
        assert first_action.radio_bytes == 8
        assert runtime._admit_action_batch("first", (first_action,)) is True
        # The second plugin has an unused per-plugin budget, but the shared
        # radio budget prevents the combined four-frame burst.
        assert runtime._admit_action_batch("second", (second_action,)) is False
        assert runtime.status()["dropped_actions"] == 1
    finally:
        runtime.close()
        store.close()


def test_radio_admission_caps_synchronous_frames_but_preserves_file_jobs(
    tmp_path,
) -> None:
    manifest = _write_plugin(
        tmp_path,
        "first",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="first", name="First", version="1.0.0")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
        config=PluginRuntimeConfig(
            chat_max_bytes=200,
            long_reply_retry_limit=0,
            max_actions_per_minute=100,
            max_synchronous_radio_frames_per_batch=66,
            max_radio_frames_per_minute=10_000,
            max_radio_bytes_per_minute=10_000_000,
            max_global_radio_frames_per_minute=10_000,
            max_global_radio_bytes_per_minute=10_000_000,
        ),
    )
    try:
        long_actions = tuple(
            runtime._queued_external_action(
                "first",
                _event(""),
                ReplyAction("x" * 4096, long=True),
            )
            for _ in range(4)
        )
        assert all(action.radio_frames == 22 for action in long_actions)
        assert runtime._admit_action_batch("first", long_actions[:3]) is True
        assert runtime._admit_action_batch("first", long_actions) is False

        queued_file = _QueuedAction(
            "first",
            _event(""),
            SendFileAction("!00000001", "sample.bin"),
            radio_frames=1_000,
            radio_bytes=1_000,
        )
        assert runtime._admit_action_batch("first", (queued_file,)) is True
        assert runtime.status()["dropped_actions"] == 4
    finally:
        runtime.close()
        store.close()


def test_accept_file_offer_reserves_worst_case_ack_airtime(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "first",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="first", name="First", version="1.0.0")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
    )
    try:
        accepted_offer = runtime._queued_external_action(
            "first",
            _event(""),
            AcceptFileOfferAction(),
        )
        expected_frames = (
            runtime._config.max_inbound_file_bytes
            + FILE_TRANSFER_CHUNK_BYTES
            - 1
        ) // FILE_TRANSFER_CHUNK_BYTES + 1
        assert accepted_offer.radio_frames == expected_frames
        assert (
            accepted_offer.radio_bytes
            == expected_frames * FILE_TRANSFER_MAX_WIRE_BYTES
        )
        assert runtime._admit_action_batch("first", (accepted_offer,)) is True
        assert (
            runtime._admit_action_batch("first", (accepted_offer,) * 7)
            is False
        )
        assert runtime.status()["dropped_actions"] == 7
    finally:
        runtime.close()
        store.close()


def test_city_aware_plugin_uses_stable_node_and_atlas_facades(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "city",
        commands=("where",),
        source="""
from meshdash.plugins import Script
script = Script(id="city", name="City", version="1.0.0")
@script.command("where")
def where(ctx):
    location = ctx.mesh.get_node_location(ctx.message.sender_id)
    city = ctx.mesh.nearest_city(location["latitude"], location["longitude"])
    return ctx.reply(city["name"])
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        node_snapshot_fn=lambda: [
            {
                "id": "!00000001",
                "position": {"latitude": 41.8781, "longitude": -87.6298},
            }
        ],
    )
    try:
        runtime.try_enqueue(_event("!where"))
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "Chicago"
    finally:
        runtime.close()
        store.close()


def test_start_and_stop_lifecycle_handlers_are_best_effort_and_stateful(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "lifecycle",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="lifecycle", name="Lifecycle", version="1.0.0")
@script.on_start
def start(ctx):
    ctx.state["started"] = int(ctx.state.get("started", 0)) + 1
@script.on_stop
def stop(ctx):
    ctx.state["stopped"] = True
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
    )
    _wait_until(lambda: store.snapshot("lifecycle", "system").state.get("started") == 1)
    runtime.close()
    assert store.snapshot("lifecycle", "system").state == {
        "started": 1,
        "stopped": True,
    }
    store.close()


def test_declared_ticker_updates_runtime_status_without_radio_action(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "ticker",
        commands=("work",),
        source="""
from meshdash.plugins import Script
script = Script(id="ticker", name="Ticker", version="1.0.0")
script.ticker("activity", label="Activity", metric=True, default_enabled=True)
@script.on_start
def start(ctx):
    ctx.set_ticker("activity", value="idle", rows={"Jobs": 0}, metric_value=0)
@script.command("work")
def work(ctx):
    ctx.set_ticker(
        "activity",
        value="1 active",
        rows={"Jobs": 1, "State": "Running"},
        state="good",
        detail="One job is running",
        metric_value=1,
    )
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    changed = threading.Event()
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        state_changed_fn=changed.set,
    )
    try:
        _wait_until(lambda: bool(runtime.status()["tickers"]))
        _wait_until(lambda: runtime.status()["tickers"][0]["value"] == "idle")  # type: ignore[index]
        initial = runtime.status()["tickers"][0]  # type: ignore[index]
        assert initial["id"] == "script:ticker:activity"
        assert initial["label"] == "Activity"
        assert initial["metric"] is True
        assert initial["rows"] == [{"key": "Jobs", "value": 0}]

        changed.clear()
        assert runtime.try_enqueue(_event("!work")) is True
        assert changed.wait(5.0)
        _wait_until(lambda: runtime.status()["tickers"][0]["value"] == "1 active")  # type: ignore[index]
        updated = runtime.status()["tickers"][0]  # type: ignore[index]
        assert updated["state"] == "good"
        assert updated["detail"] == "One job is running"
        assert updated["metric_value"] == 1
        assert sends == []

        runtime.reconfigure(())
        _wait_until(lambda: runtime.status()["tickers"] == [])
    finally:
        runtime.close()
        store.close()


def test_full_event_queue_never_blocks_receive_side_enqueue(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "slow",
        commands=("slow",),
        source="""
from meshdash.plugins import Script
script = Script(id="slow", name="Slow", version="1.0.0")
@script.command("slow")
def slow(ctx):
    while True:
        pass
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **_kwargs: None,
        config=PluginRuntimeConfig(
            event_queue_size=1,
            handler_timeout_seconds=0.5,
            startup_timeout_seconds=3,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("!slow", packet_id=1)) is True
        _wait_until(lambda: runtime.status()["current_plugin"] == "slow")
        assert runtime.try_enqueue(_event("!slow", packet_id=2)) is True
        started = time.monotonic()
        assert runtime.try_enqueue(_event("!slow", packet_id=3)) is False
        assert time.monotonic() - started < 0.05
        assert runtime.status()["dropped_events"] == 1
    finally:
        runtime.close()
        store.close()


def test_invalid_session_action_rejects_entire_state_and_action_batch(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "public",
        commands=(),
        source="""
from meshdash.plugins import Script
script = Script(id="public", name="Public", version="1.0.0")
@script.on_message
def message(ctx):
    ctx.state["must_rollback"] = True
    ctx.session.start()
    return ctx.reply("must not send")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
    )
    try:
        _wait_until(lambda: bool(runtime.status()["plugins"]))
        broadcast = MessageEvent(
            text="hello",
            sender_id="!00000001",
            destination_id="^all",
            local_node_id="!00000002",
            channel_index=0,
            is_direct=False,
            is_broadcast=True,
            packet_id=20,
            reply_packet_id=None,
            received_at=time.time(),
        )
        assert runtime.try_enqueue(broadcast) is True
        _wait_until(lambda: "direct messages" in str(runtime.status()["last_error"]))
        assert store.snapshot("public", "!00000001").state == {}
        assert sends == []
    finally:
        runtime.close()
        store.close()


def test_full_action_queue_rejects_state_commit_for_entire_result(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "effects",
        commands=("effect",),
        source="""
from meshdash.plugins import Script
script = Script(id="effects", name="Effects", version="1.0.0")
@script.command("effect")
def effect(ctx):
    ctx.state["handled"] = int(ctx.state.get("handled", 0)) + 1
    return ctx.reply("effect")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    send_started = threading.Event()
    release_send = threading.Event()

    def _blocking_send(**_kwargs: object) -> None:
        send_started.set()
        release_send.wait(timeout=3)

    runtime = PluginRuntime(
        manifests=[manifest],
        state_store=store,
        send_chat_fn=_blocking_send,
        config=PluginRuntimeConfig(action_queue_size=1),
    )
    try:
        runtime.try_enqueue(_event("!effect", packet_id=31))
        assert send_started.wait(timeout=3)
        runtime.try_enqueue(_event("!effect", packet_id=32))
        _wait_until(lambda: store.snapshot("effects", "!00000001").state.get("handled") == 2)
        runtime.try_enqueue(_event("!effect", packet_id=33))
        _wait_until(lambda: int(runtime.status()["dropped_actions"]) >= 1)
        assert store.snapshot("effects", "!00000001").state == {"handled": 2}
    finally:
        release_send.set()
        runtime.close()
        store.close()


def test_import_time_hang_is_quarantined_without_starving_healthy_plugin(tmp_path) -> None:
    hung = _write_plugin(
        tmp_path,
        "importhang",
        commands=(),
        source="""
while True:
    pass
""",
    )
    healthy = _write_plugin(
        tmp_path,
        "afterhang",
        commands=("after",),
        source="""
from meshdash.plugins import Script
script = Script(id="afterhang", name="Afterhang", version="1.0.0")
@script.command("after")
def after(ctx):
    return ctx.reply("healthy loaded")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[hung, healthy],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        config=PluginRuntimeConfig(
            startup_timeout_seconds=0.2,
            handler_timeout_seconds=1,
            restart_backoff_seconds=0.01,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("!after")) is True
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "healthy loaded"
        assert int(runtime.status()["generation"]) >= 2
        assert "quarantined" in runtime.status()["plugins"]["importhang"]["error"]  # type: ignore[index]
    finally:
        runtime.close()
        store.close()


def test_fatal_import_exit_is_attributed_quarantined_and_does_not_respawn_loop(
    tmp_path,
) -> None:
    fatal = _write_plugin(
        tmp_path,
        "fatal",
        commands=(),
        source="""
import os
os._exit(23)
""",
    )
    healthy = _write_plugin(
        tmp_path,
        "survivor",
        commands=("survive",),
        source="""
from meshdash.plugins import Script
script = Script(id="survivor", name="Survivor", version="1.0.0")
@script.command("survive")
def survive(ctx):
    return ctx.reply("loaded after fatal import")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[fatal, healthy],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        config=PluginRuntimeConfig(
            startup_timeout_seconds=1,
            handler_timeout_seconds=1,
            restart_backoff_seconds=0.01,
            max_restart_backoff_seconds=0.04,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("!survive")) is True
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "loaded after fatal import"
        status = runtime.status()
        fatal_status = status["plugins"]["fatal"]  # type: ignore[index]
        assert "quarantined" in fatal_status["error"]
        assert "disable and re-enable" in fatal_status["error"]
        assert "code 23" in fatal_status["last_error"]
        assert fatal_status["failures"] == 1
        assert status["generation"] == 2
        assert status["restarts"] == 1
        assert status["consecutive_start_failures"] == 0
        time.sleep(0.1)
        assert runtime.status()["generation"] == 2
    finally:
        runtime.close()
        store.close()


def test_startup_quarantine_retries_only_after_explicit_disable_and_reenable(
    tmp_path,
) -> None:
    import_marker = tmp_path / "flaky-imported"
    flaky = _write_plugin(
        tmp_path,
        "flaky",
        commands=("flaky",),
        source=f"""
from pathlib import Path
marker = Path({str(import_marker)!r})
if not marker.exists():
    marker.write_text("attempted", encoding="utf-8")
    while True:
        pass
from meshdash.plugins import Script
script = Script(id="flaky", name="Flaky", version="1.0.0")
@script.command("flaky")
def flaky(ctx):
    return ctx.reply("flaky recovered")
""",
    )
    healthy = _write_plugin(
        tmp_path,
        "steady",
        commands=("steady",),
        source="""
from meshdash.plugins import Script
script = Script(id="steady", name="Steady", version="1.0.0")
@script.command("steady")
def steady(ctx):
    return ctx.reply("steady loaded")
""",
    )
    store = PluginStateStore(str(tmp_path / "state.sqlite3"))
    sends: list[dict[str, object]] = []
    runtime = PluginRuntime(
        manifests=[flaky, healthy],
        state_store=store,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)),
        config=PluginRuntimeConfig(
            startup_timeout_seconds=0.2,
            handler_timeout_seconds=1,
            restart_backoff_seconds=0.01,
        ),
    )
    try:
        assert runtime.try_enqueue(_event("!steady")) is True
        _wait_until(lambda: len(sends) == 1)
        assert sends[0]["text"] == "steady loaded"
        quarantined_generation = runtime.status()["generation"]
        time.sleep(0.1)
        assert runtime.status()["generation"] == quarantined_generation

        runtime.reconfigure([healthy])
        runtime.reconfigure([flaky, healthy])

        def _flaky_is_loaded() -> bool:
            plugins = runtime.status()["plugins"]
            if not isinstance(plugins, dict):
                return False
            registration = plugins.get("flaky", {})
            return isinstance(registration, dict) and not registration.get("error")

        _wait_until(_flaky_is_loaded)
        assert runtime.try_enqueue(_event("!flaky", packet_id=22)) is True
        _wait_until(lambda: len(sends) == 2)
        assert sends[1]["text"] == "flaky recovered"
        assert int(runtime.status()["generation"]) >= 3
    finally:
        runtime.close()
        store.close()
