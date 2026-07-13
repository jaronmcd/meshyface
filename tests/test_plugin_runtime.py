import os
import threading
import time
from pathlib import Path

from meshdash.bots import MessageEvent, ReplyAction, parse_manifest
from meshdash.plugin_runtime import (
    PluginRuntime,
    PluginRuntimeConfig,
    _QueuedAction,
    _QueuedActionBatch,
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
    (directory / "bot.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                f'id = "{plugin_id}"',
                f'name = "{plugin_id.title()}"',
                'version = "1.0.0"',
                'entrypoint = "bot.py:bot"',
                f"commands = [{command_toml}]",
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (directory / "bot.py").write_text(source, encoding="utf-8")
    return parse_manifest(directory / "bot.toml")


def _event(
    text: str,
    *,
    packet_id: int = 10,
    packet: dict[str, object] | None = None,
) -> MessageEvent:
    return MessageEvent(
        text=text,
        sender_id="!00000001",
        destination_id="!00000002",
        local_node_id="!00000002",
        channel_index=0,
        is_direct=True,
        is_broadcast=False,
        packet_id=packet_id,
        reply_packet_id=None,
        received_at=time.time(),
        packet=packet,
        portnum="POSITION_APP" if packet is not None else "",
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
from meshdash.bots import Bot

bot = Bot(id="example", name="Example", version="1.0.0")

@bot.command("hello")
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


def test_packet_handler_runs_inside_worker_with_raw_packet_context(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "packets",
        commands=(),
        source="""
from meshdash.bots import Bot
bot = Bot(id="packets", name="Packets", version="1.0.0")
@bot.on_packet
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


def test_quit_never_waits_for_sqlite_on_the_receive_callback(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "sessions",
        commands=(),
        source="""
from meshdash.bots import Bot
bot = Bot(id="sessions", name="Sessions", version="1.0.0")
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
from meshdash.bots import Bot
bot = Bot(id="idle", name="Idle", version="1.0.0")
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
from meshdash.bots import Bot
bot = Bot(id="hung", name="Hung", version="1.0.0")
@bot.command("hang")
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
from meshdash.bots import Bot
bot = Bot(id="healthy", name="Healthy", version="1.0.0")
@bot.command("ok")
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
from meshdash.bots import Bot
bot = Bot(id="broken", name="Broken", version="1.0.0")
@bot.command("fail")
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


def test_city_aware_plugin_uses_stable_node_and_atlas_facades(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "city",
        commands=("where",),
        source="""
from meshdash.bots import Bot
bot = Bot(id="city", name="City", version="1.0.0")
@bot.command("where")
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
from meshdash.bots import Bot
bot = Bot(id="lifecycle", name="Lifecycle", version="1.0.0")
@bot.on_start
def start(ctx):
    ctx.state["started"] = int(ctx.state.get("started", 0)) + 1
@bot.on_stop
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


def test_full_event_queue_never_blocks_receive_side_enqueue(tmp_path) -> None:
    manifest = _write_plugin(
        tmp_path,
        "slow",
        commands=("slow",),
        source="""
from meshdash.bots import Bot
bot = Bot(id="slow", name="Slow", version="1.0.0")
@bot.command("slow")
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
from meshdash.bots import Bot
bot = Bot(id="public", name="Public", version="1.0.0")
@bot.on_message
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
from meshdash.bots import Bot
bot = Bot(id="effects", name="Effects", version="1.0.0")
@bot.command("effect")
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
from meshdash.bots import Bot
bot = Bot(id="afterhang", name="Afterhang", version="1.0.0")
@bot.command("after")
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


def test_expired_startup_quarantine_reloads_plugin_into_worker(tmp_path) -> None:
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
from meshdash.bots import Bot
bot = Bot(id="flaky", name="Flaky", version="1.0.0")
@bot.command("flaky")
def flaky(ctx):
    return ctx.reply("flaky recovered")
""",
    )
    healthy = _write_plugin(
        tmp_path,
        "steady",
        commands=("steady",),
        source="""
from meshdash.bots import Bot
bot = Bot(id="steady", name="Steady", version="1.0.0")
@bot.command("steady")
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
        runtime._plugin_quarantined_until["flaky"] = 0.0

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
