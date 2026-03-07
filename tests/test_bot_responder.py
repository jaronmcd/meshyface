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
    assert "hops=" in str(sent[0]["text"]).lower()


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
    assert bot is None
