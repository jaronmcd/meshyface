import json

from meshdash.bot_responder import MeshResponseBot, build_mesh_response_bot_from_env


class _FakeIface:
    def __init__(self):
        self.nodesByNum = {
            0x02ED9B7C: {
                "user": {
                    "id": "!02ed9b7c",
                    "shortName": "9b7c",
                    "longName": "Crash Override",
                },
                "lastHeard": 1710001200,
                "hopsAway": 0,
            },
            0x49B5DFF0: {
                "user": {
                    "id": "!49b5dff0",
                    "shortName": "dff0",
                    "longName": "Brew HQ",
                },
                "lastHeard": 1710001100,
                "hopsAway": 3,
            },
            0x11B8D868: {
                "user": {
                    "id": "!11b8d868",
                    "shortName": "d868",
                    "longName": "Mesh Node",
                },
                "lastHeard": 1710000900,
                "hopsAway": 4,
            },
        }


def _base_packet(text: str, *, packet_id: int = 1001, to_id: str = "^all") -> dict[str, object]:
    return {
        "id": packet_id,
        "fromId": "!49b5dff0",
        "toId": to_id,
        "from": 0x49B5DFF0,
        "to": 0xFFFFFFFF,
        "rxTime": 1710001234,
        "hopStart": 5,
        "hopLimit": 2,
        "channel": 0,
        "decoded": {
            "portnum": "TEXT_MESSAGE_APP",
            "text": text,
        },
    }


def test_ping_targeted_to_local_suffix_replies_with_pong():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("ping 9b7c"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "^all"
    assert sent[0]["reply_id"] == 1001
    assert sent[0]["channel_index"] == 0
    assert "pong" in str(sent[0]["text"]).lower()
    assert "hop " in str(sent[0]["text"]).lower()
    assert "6.0s" in str(sent[0]["text"]).lower()
    assert "rx=" not in str(sent[0]["text"]).lower()
    assert "tx=" not in str(sent[0]["text"]).lower()


def test_ping_targeted_to_other_suffix_is_ignored():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("ping dead"), iface)

    assert sent == []


def test_whois_unknown_replies_with_unknown():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("whois ffff"), iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "whois ffff" in text
    assert "unknown" in text


def test_custom_command_replies_with_template_values():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={
            "status": "status local={local_id} from={from_id} hops={hops}",
        },
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("!status"), iface)

    assert len(sent) == 1
    text = str(sent[0]["text"])
    assert "local=!02ed9b7c" in text
    assert "from=!49b5dff0" in text
    assert "hops=3" in text


def test_build_bot_from_env_can_disable_bot():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "0"},
    )
    assert bot is not None
    assert bot.enabled is False
    assert bot.log_enabled is True


def test_build_bot_from_env_defaults_bot_responses_to_disabled():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={},
    )
    assert bot is not None
    assert bot.enabled is False
    assert bot.log_enabled is True
    assert bot.game_enabled is True
    settings = bot.bot_settings()
    enabled_names = [row["name"] for row in settings["commands"] if row["enabled"]]
    assert enabled_names == ["ping", "zork"]


def test_build_bot_from_env_can_disable_bot_and_logging():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_ENABLED": "0",
            "MESH_DASH_BOT_LOG_ENABLED": "0",
        },
    )
    assert bot is None


def test_bot_logs_requests_when_responses_disabled():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        enabled=False,
        log_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("ping 9b7c"), iface)

    assert sent == []
    history = bot.recent_requests()
    assert len(history) == 1
    row = history[0]
    assert row["command"] == "ping 9b7c"
    assert row["from_id"] == "!49b5dff0"
    assert row["to_id"] == "^all"
    assert row["respond_enabled"] is False
    assert row["responded"] is False


def test_bot_settings_expose_managed_command_catalog():
    bot = MeshResponseBot(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={"status": "ok"},
        game_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )

    settings = bot.bot_settings()
    commands = settings["commands"]
    names = {row["name"] for row in commands}

    assert "ping" in names
    assert "zork" in names
    assert "status" in names
    assert commands[0]["name"] == "ping"
    assert commands[1]["name"] == "zork"
    ping = next(row for row in commands if row["name"] == "ping")
    assert ping["enabled"] is True


def test_ping_command_can_be_disabled_without_disabling_bot():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.configure(command_settings={"ping": False})
    bot.on_receive(_base_packet("ping 9b7c"), iface)

    assert sent == []
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command_head"] == "ping"
    assert history[0]["command_enabled"] is False
    settings = bot.bot_settings()
    ping = next(row for row in settings["commands"] if row["name"] == "ping")
    assert ping["enabled"] is False


def test_ping_formats_long_round_trip_as_human_readable_duration():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: 1710001240.0,
    )
    packet = _base_packet("ping 9b7c")
    packet["rxTime"] = 1709995707
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "pong" in text
    assert "1h 32m 13s" in text


def test_zork_game_starts_only_for_direct_messages():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2001, to_id="^all"), iface)
    bot.on_receive(_base_packet("zork", packet_id=2002, to_id="!02ed9b7c"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "!49b5dff0"
    assert "zork" in str(sent[0]["text"]).lower()


def test_zork_game_session_replies_to_followup_commands():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2101, to_id="!02ed9b7c"), iface)
    bot.on_receive(_base_packet("look", packet_id=2102, to_id="!02ed9b7c"), iface)

    assert len(sent) == 2
    assert sent[1]["destination"] == "!49b5dff0"
    assert "trailhead" in str(sent[1]["text"]).lower()
    history = bot.recent_requests()
    assert len(history) == 2
    assert all(str(row.get("command_head") or "") == "zork" for row in history)


def test_zork_game_disabled_still_logs_direct_start_requests():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=False,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2201, to_id="!02ed9b7c"), iface)

    assert sent == []
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command"] == "zork"
    assert history[0]["command_head"] == "zork"


def test_build_bot_from_env_can_enable_game_mode():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_GAME_ENABLED": "1"},
    )
    assert bot is not None
    assert bot.enabled is False
    assert bot.game_enabled is True


def test_build_bot_from_env_can_disable_specific_command():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_DISABLED_COMMANDS": "ping,whois"},
    )
    assert bot is not None
    settings = bot.bot_settings()
    ping = next(row for row in settings["commands"] if row["name"] == "ping")
    whois = next(row for row in settings["commands"] if row["name"] == "whois")
    assert ping["enabled"] is False
    assert whois["enabled"] is False


def test_build_bot_from_env_empty_disabled_commands_enables_full_catalog():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_DISABLED_COMMANDS": ""},
    )
    assert bot is not None
    settings = bot.bot_settings()
    rows = {row["name"]: row for row in settings["commands"]}
    assert rows["ping"]["enabled"] is True
    assert rows["zork"]["enabled"] is True
    assert rows["cmd"]["enabled"] is True
    assert rows["whois"]["enabled"] is True


def test_bot_settings_are_persisted_and_loaded_from_file(tmp_path):
    settings_path = tmp_path / "bot_settings.json"

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert bot is not None

    saved = bot.configure(
        enabled=True,
        game_enabled=False,
        command_settings={"whois": True},
    )
    assert saved["ok"] is True
    assert settings_path.exists()

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["enabled"] is True
    assert payload["game_enabled"] is False
    assert "whois" not in payload["disabled_commands"]
    assert "cmd" in payload["disabled_commands"]

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.enabled is True
    assert loaded.game_enabled is False

    rows = {row["name"]: row for row in loaded.bot_settings()["commands"]}
    assert rows["ping"]["enabled"] is True
    assert rows["zork"]["enabled"] is False
    assert rows["whois"]["enabled"] is True
    assert rows["cmd"]["enabled"] is False


def test_explicit_env_bot_settings_override_persisted_file(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
            }
        ),
        encoding="utf-8",
    )

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_SETTINGS_FILE": str(settings_path),
            "MESH_DASH_BOT_ENABLED": "0",
            "MESH_DASH_BOT_DISABLED_COMMANDS": "ping",
        },
    )
    assert bot is not None
    assert bot.enabled is False
    settings = bot.bot_settings()
    rows = {row["name"]: row for row in settings["commands"]}
    assert rows["ping"]["enabled"] is False
    assert rows["whois"]["enabled"] is True
    assert rows["zork"]["enabled"] is False
