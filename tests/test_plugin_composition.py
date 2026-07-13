import time
from pathlib import Path
from types import SimpleNamespace

from meshdash.file_transfer_protocol import (
    FILE_TRANSFER_PORTNUM,
    build_file_transfer_ack_frame,
    encode_file_transfer_frame,
    parse_file_transfer_frame_text,
)
from meshdash.plugin_composition import build_plugin_subsystem


class _Tracker:
    def __init__(self) -> None:
        self.listeners: list[object] = []

    def add_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.append(listener)

    def remove_accepted_packet_listener(self, listener: object) -> None:
        self.listeners.remove(listener)


def _args(tmp_path: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "bots_directory": str(tmp_path / "plugins"),
        "bots_state_db": str(tmp_path / "plugin-state.sqlite3"),
        "bots_files_directory": str(tmp_path / "files"),
        "bots_event_queue_size": 8,
        "bots_handler_timeout": 1.0,
        "bot_enable": [],
        "bot_disable": [],
        "file_transfer_enable": False,
        "file_transfer_max_bytes": 4096,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _write_echo_plugin(root: Path, *, default_enabled: bool = False) -> None:
    directory = root / "echo"
    directory.mkdir(parents=True)
    (directory / "bot.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "echo"',
                'name = "Echo"',
                'version = "1.0.0"',
                'entrypoint = "bot.py:bot"',
                'commands = ["echo"]',
                f"default_enabled = {str(default_enabled).lower()}",
            )
        ),
        encoding="utf-8",
    )
    (directory / "bot.py").write_text(
        """
from meshdash.bots import Bot
bot = Bot(id="echo", name="Echo", version="1.0.0")
@bot.command("echo")
def echo(ctx):
    return ctx.reply("echo works")
""",
        encoding="utf-8",
    )


def _wait_until(predicate, timeout: float = 4.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition did not become true")


def test_enabled_master_with_no_enabled_plugins_starts_no_worker_or_dispatcher(tmp_path) -> None:
    tracker = _Tracker()
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        status = subsystem.status()
        assert status["enabled"] is True
        assert status["discovered"] == 0
        assert status["runtime"] == {}
        assert tracker.listeners == []
    finally:
        subsystem.close()


def test_individual_enablement_loads_in_worker_and_routes_accepted_event(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path, bot_enable=["echo"]),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert len(tracker.listeners) == 1, subsystem.status()
        listener = tracker.listeners[0]
        listener(  # type: ignore[operator]
            {
                "from": 1,
                "to": 2,
                "id": 99,
                "channel": 0,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!echo"},
            },
            object(),
        )
        _wait_until(lambda: bool(sends))
        assert sends[0]["text"] == "echo works"
        status = subsystem.status()
        assert status["enabled_plugins"] == ["echo"]
        assert status["runtime"]["status"] == "running"  # type: ignore[index]
        assert status["runtime"]["worker_alive"] is True  # type: ignore[index]
        assert status["scripts"][0]["runtime_status"] == "running"  # type: ignore[index]
        assert status["scripts"][0]["runtime_error"] == ""  # type: ignore[index]
        assert status["scripts"][0]["restart_required"] is False  # type: ignore[index]
    finally:
        subsystem.close()
    assert tracker.listeners == []


def test_individual_enablement_persists_for_the_next_runtime(tmp_path) -> None:
    plugin_root = tmp_path / "plugins"
    _write_echo_plugin(plugin_root)
    args = _args(tmp_path)
    first = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert first.status()["enabled_plugins"] == []
        assert first.set_plugin_enabled("echo", True) == {
            "ok": True,
            "plugin_id": "echo",
            "enabled": True,
            "restart_required": True,
        }
        script = first.status()["scripts"][0]  # type: ignore[index]
        assert script["runtime_status"] == "restart_pending"
        assert script["restart_required"] is True
    finally:
        first.close()

    second = build_plugin_subsystem(
        args=args,
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert second.status()["enabled_plugins"] == ["echo"]
    finally:
        second.close()


def test_broken_plugin_is_reported_without_preventing_healthy_plugin(tmp_path) -> None:
    root = tmp_path / "plugins"
    _write_echo_plugin(root, default_enabled=True)
    broken = root / "broken"
    broken.mkdir()
    (broken / "bot.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "broken"',
                'name = "Broken"',
                'version = "1.0.0"',
                'entrypoint = "bot.py:bot"',
                "commands = []",
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (broken / "bot.py").write_text(
        "raise RuntimeError(f'import failed at {__file__}')\n",
        encoding="utf-8",
    )
    subsystem = build_plugin_subsystem(
        args=_args(tmp_path),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=_Tracker(),
        send_chat_fn=lambda **_kwargs: {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        assert subsystem.status()["error"] == ""
        _wait_until(
            lambda: bool(subsystem.status().get("runtime", {}).get("plugins"))  # type: ignore[union-attr]
        )
        status = subsystem.status()
        plugins = status["runtime"]["plugins"]  # type: ignore[index]
        assert status["runtime"]["worker_alive"] is True  # type: ignore[index]
        assert status["runtime"]["status"] == "running"  # type: ignore[index]
        assert "import failed" in plugins["broken"]["error"]
        assert "[path]" in plugins["broken"]["error"]
        assert plugins["echo"].get("error") is None
        scripts = {row["id"]: row for row in status["scripts"]}  # type: ignore[index]
        assert scripts["broken"]["runtime_status"] == "error"
        assert "import failed" in scripts["broken"]["runtime_error"]
        assert scripts["echo"]["runtime_status"] == "running"
        assert scripts["echo"]["runtime_error"] == ""
        assert str(tmp_path) not in str(status["runtime"])
        assert str(tmp_path) not in str(status["scripts"])
    finally:
        subsystem.close()


def test_plugin_file_action_queues_host_managed_outbound_job(tmp_path) -> None:
    root = tmp_path / "plugins"
    directory = root / "files"
    directory.mkdir(parents=True)
    (directory / "bot.toml").write_text(
        "\n".join(
            (
                "api_version = 1",
                'id = "files"',
                'name = "Files"',
                'version = "1.0.0"',
                'entrypoint = "bot.py:bot"',
                'commands = ["file"]',
                "default_enabled = true",
            )
        ),
        encoding="utf-8",
    )
    (directory / "bot.py").write_text(
        """
from meshdash.bots import Bot
bot = Bot(id="files", name="Files", version="1.0.0")
@bot.command("file")
def send_file(ctx):
    return ctx.mesh.send_file(ctx.message.sender_id, "sample.bin")
""",
        encoding="utf-8",
    )
    approved = tmp_path / "files"
    approved.mkdir()
    (approved / "sample.bin").write_bytes(b"plugin file payload")
    tracker = _Tracker()
    sends: list[dict[str, object]] = []
    subsystem = build_plugin_subsystem(
        args=_args(
            tmp_path,
            file_transfer_enable=True,
            bots_files_directory=str(approved),
        ),
        iface=SimpleNamespace(nodesByNum={}),
        tracker=tracker,
        send_chat_fn=lambda **kwargs: sends.append(dict(kwargs)) or {"ok": True},
        local_node_id_fn=lambda: "!00000002",
    )
    try:
        tracker.listeners[0](  # type: ignore[operator]
            {
                "from": 1,
                "to": 2,
                "id": 101,
                "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!file"},
            },
            object(),
        )
        _wait_until(
            lambda: any(str(send.get("text") or "").startswith("MF_FILE_V2|M|") for send in sends)
        )
        metadata_text = next(
            str(send["text"])
            for send in sends
            if str(send.get("text") or "").startswith("MF_FILE_V2|M|")
        )
        metadata = parse_file_transfer_frame_text(metadata_text)
        assert metadata is not None
        transfer_id = str(metadata["transfer_id"])
        total_chunks = int(metadata["total_chunks"])

        def _deliver_ack(received_indexes: object, packet_id: int) -> None:
            ack_text = build_file_transfer_ack_frame(
                transfer_id=transfer_id,
                total_chunks=total_chunks,
                received_indexes=received_indexes,
            )
            ack = parse_file_transfer_frame_text(ack_text)
            assert ack is not None
            tracker.listeners[0](  # type: ignore[operator]
                {
                    "from": 1,
                    "to": 2,
                    "id": packet_id,
                    "channel": 0,
                    "decoded": {
                        "portnum": FILE_TRANSFER_PORTNUM,
                        "payload": encode_file_transfer_frame(ack),
                    },
                },
                object(),
            )

        _deliver_ack((), 201)
        _wait_until(
            lambda: sum(
                str(send.get("text") or "").startswith("MF_FILE_V2|C|")
                for send in sends
            )
            == total_chunks
        )
        _deliver_ack(range(total_chunks), 202)
        _wait_until(
            lambda: subsystem.status()["file_jobs"]["completed_count"] == 1  # type: ignore[index]
        )
        file_status = subsystem.status()["file_jobs"]
        assert file_status["submitted_count"] == 1  # type: ignore[index]
        assert file_status["completed_count"] == 1  # type: ignore[index]
    finally:
        subsystem.close()
