import json

import meshdash.bot_responder as _bot_responder_module
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


def _segment_marker(text: object) -> tuple[int | None, int | None, str]:
    raw = str(text or "")
    head, sep, tail = raw.partition(" ")
    if not sep or "/" not in head:
        return (None, None, raw)
    left, right = head.split("/", 1)
    if left.isdigit() and right.isdigit():
        return (int(left), int(right), tail)
    return (None, None, raw)


def _joined_segment_text(rows: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for row in rows:
        _part, _total, body = _segment_marker(row.get("text"))
        clean = str(body or "").strip()
        if clean:
            parts.append(clean)
    return " ".join(parts)


class _FakeTimer:
    def __init__(self, delay_seconds, callback):
        self.delay_seconds = float(delay_seconds)
        self._callback = callback
        self.cancelled = False
        self.started = False
        self.daemon = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if self.cancelled:
            return
        self._callback()


class _FakeTimerFactory:
    def __init__(self):
        self.timers = []

    def __call__(self, delay_seconds, callback):
        timer = _FakeTimer(delay_seconds, callback)
        self.timers.append(timer)
        return timer


def test_ping_targeted_to_local_suffix_replies_with_human_readable_reply():
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
    bot.on_receive(_base_packet("ping 9b7c"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "^all"
    assert sent[0]["reply_id"] == 1001
    assert sent[0]["channel_index"] == 0
    text = str(sent[0]["text"]).lower()
    assert "brew hq" not in text
    assert text.startswith("3 hops")
    assert "request age" not in text
    assert "3 hops" in text
    assert "pong" not in text
    assert "rx=" not in text
    assert "tx=" not in text


def test_test_alias_replies_with_human_readable_ping_text_and_logs_as_ping():
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
    bot.on_receive(_base_packet("test"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "^all"
    assert sent[0]["reply_id"] == 1001
    text = str(sent[0]["text"]).lower()
    assert "brew hq" not in text
    assert "hops" in text
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command"] == "test"
    assert history[0]["command_head"] == "ping"


def test_natural_ping_phrase_replies_with_human_readable_ping_text():
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
    bot.on_receive(_base_packet("can you see this?"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "^all"
    assert sent[0]["reply_id"] == 1001
    text = str(sent[0]["text"]).lower()
    assert "brew hq" not in text
    assert "hops" in text
    assert "hops" in text
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command"] == "can you see this?"
    assert history[0]["command_head"] == "ping"


def test_natural_ping_phrase_ignores_extra_trailing_words():
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
    bot.on_receive(_base_packet("can you see this? 9b7c"), iface)

    assert sent == []
    assert bot.recent_requests() == []


def test_natural_joke_trigger_replies_with_random_joke_and_logs_as_joke():
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
    bot.on_receive(_base_packet("tell me a joke"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "^all"
    assert sent[0]["reply_id"] == 1001
    assert str(sent[0]["text"]).strip()
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command"] == "tell me a joke"
    assert history[0]["command_head"] == "joke"


def test_nodename_placeholder_triggers_match_with_and_without_prefix():
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
    bot.on_receive(_base_packet("crash override ping", packet_id=1001), iface)
    bot.on_receive(_base_packet("ping", packet_id=1002), iface)

    assert len(sent) == 2
    history = bot.recent_requests()
    assert len(history) == 2
    assert history[0]["command_head"] == "ping"
    assert history[1]["command_head"] == "ping"


def test_joke_trigger_and_joke_lines_are_configurable():
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
    bot.configure(
        joke_triggers=["make me laugh"],
        joke_lines=["mesh joke one", "mesh joke two"],
    )
    bot.on_receive(_base_packet("tell me a joke"), iface)
    bot.on_receive(_base_packet("make me laugh", packet_id=1002), iface)

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() in {"mesh joke one", "mesh joke two"}
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command_head"] == "joke"


def test_zork_start_triggers_are_configurable_with_nodename_placeholder():
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
    bot.configure(zork_triggers=["{nodename} play zork"])

    bot.on_receive(_base_packet("zork", packet_id=1001, to_id="!02ed9b7c"), iface)
    assert sent == []

    bot.on_receive(_base_packet("play zork", packet_id=1002, to_id="!02ed9b7c"), iface)
    assert sent
    assert any("session started" in str(row.get("text") or "").lower() for row in sent)

    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command"] == "play zork"
    assert history[0]["command_head"] == "zork"
    assert history[0]["responded"] is True


def test_joke_rotation_avoids_repeats_until_cycle_resets():
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
    bot.configure(joke_lines=["j1", "j2", "j3"])
    bot.on_receive(_base_packet("joke", packet_id=1101), iface)
    bot.on_receive(_base_packet("joke", packet_id=1102), iface)
    bot.on_receive(_base_packet("joke", packet_id=1103), iface)
    bot.on_receive(_base_packet("joke", packet_id=1104), iface)

    assert len(sent) == 4
    first_cycle = {str(row["text"]).strip() for row in sent[:3]}
    assert first_cycle == {"j1", "j2", "j3"}
    assert str(sent[3]["text"]).strip() in {"j1", "j2", "j3"}


def test_joke_command_can_be_disabled_without_disabling_bot():
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
    bot.configure(command_settings={"joke": False})
    bot.on_receive(_base_packet("joke"), iface)

    assert sent == []
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["command_head"] == "joke"
    assert history[0]["command_enabled"] is False


def test_joke_delay_punchline_waits_for_reply_before_sending_punchline():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why did the packet cross the mesh? Better line of sight."],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1301), iface)

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "Why did the packet cross the mesh?"
    assert len(fake_timers.timers) == 1
    assert fake_timers.timers[0].started is True
    assert fake_timers.timers[0].cancelled is False

    bot.on_receive(_base_packet("no clue", packet_id=1302), iface)

    assert len(sent) == 2
    assert str(sent[1]["text"]).strip() == "Better line of sight."
    assert sent[1]["reply_id"] == 1302
    assert fake_timers.timers[0].cancelled is True


def test_joke_delay_punchline_sends_timeout_punchline_after_delay():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why was the telemetry calm? It had stable readings."],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1401), iface)

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "Why was the telemetry calm?"
    assert len(fake_timers.timers) == 1

    fake_timers.timers[0].fire()

    assert len(sent) == 2
    assert str(sent[1]["text"]).strip() == "It had stable readings."
    assert sent[1]["reply_id"] == 1401


def test_joke_delay_punchline_sends_close_guess_variant_when_reply_matches():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why did the packet cross the mesh? Better line of sight."],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1501), iface)

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "Why did the packet cross the mesh?"

    bot.on_receive(_base_packet("line of sight", packet_id=1502), iface)

    assert len(sent) == 2
    reply_text = str(sent[1]["text"]).strip().lower()
    assert reply_text.startswith("nice guess, close enough.")
    assert "better line of sight." in reply_text
    assert sent[1]["reply_id"] == 1502
    assert fake_timers.timers[0].cancelled is True


def test_joke_delay_punchline_uses_custom_near_guess_template():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why did the packet cross the mesh? Better line of sight."],
        joke_near_guess_lines=["You nailed it: {punchline}"],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1503), iface)
    bot.on_receive(_base_packet("line of sight", packet_id=1504), iface)

    assert len(sent) == 2
    assert str(sent[1]["text"]).strip() == "You nailed it: Better line of sight."
    assert sent[1]["reply_id"] == 1504
    assert fake_timers.timers[0].cancelled is True


def test_joke_delay_punchline_template_without_placeholder_hides_punchline():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why did the packet cross the mesh? Better line of sight."],
        joke_near_guess_lines=["Nope. Try harder."],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1507), iface)
    bot.on_receive(_base_packet("line of sight", packet_id=1508), iface)

    assert len(sent) == 2
    assert str(sent[1]["text"]).strip() == "Nope. Try harder."
    assert sent[1]["reply_id"] == 1508
    assert fake_timers.timers[0].cancelled is True


def test_joke_delay_punchline_with_empty_near_guess_lines_uses_plain_punchline():
    iface = _FakeIface()
    sent = []
    fake_timers = _FakeTimerFactory()

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        joke_lines=["Why did the packet cross the mesh? Better line of sight."],
        joke_near_guess_lines=[],
        joke_delay_punchline_enabled=True,
        timer_factory=fake_timers,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("joke", packet_id=1505), iface)
    bot.on_receive(_base_packet("line of sight", packet_id=1506), iface)

    assert len(sent) == 2
    assert str(sent[1]["text"]).strip() == "Better line of sight."
    assert sent[1]["reply_id"] == 1506
    assert fake_timers.timers[0].cancelled is True


def test_direct_ping_replies_direct_with_reply_id():
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
    bot.on_receive(_base_packet("ping 9b7c", to_id="!02ed9b7c"), iface)

    assert len(sent) == 1
    assert sent[0]["destination"] == "!49b5dff0"
    assert sent[0]["reply_id"] == 1001
    assert "hops" in str(sent[0]["text"]).lower()


def test_ping_response_template_supports_sender_and_hops_tokens():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        ping_response_template="Hey $sender, you are $hops hops away!",
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("ping 9b7c"), iface)

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "Hey Brew HQ, you are 3 hops away!"


def test_ping_response_template_can_be_cleared_to_restore_default_reply():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        ping_response_template="$sender/$hops",
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("ping 9b7c", packet_id=1001), iface)
    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "Brew HQ/3"

    saved = bot.configure(ping_response_template="")
    assert saved["ping_response_template"] == ""
    bot.on_receive(_base_packet("ping 9b7c", packet_id=1002), iface)

    assert len(sent) == 2
    assert str(sent[1]["text"]).lower().startswith("3 hops")


def test_ping_response_template_supports_location_token_from_bot_city():
    iface = _FakeIface()
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 44.9537,
        "longitude": -93.0900,
    }
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        ping_response_template="$hops hops to $location",
        now_unix_fn=lambda: 1710001240.0,
    )
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Saint Paul",
        "state": "Minnesota",
        "country": "United States of America",
        "distance_km": 2.2,
    }
    try:
        bot.on_receive(_base_packet("ping 9b7c"), iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "3 hops to Saint Paul, Minnesota"


def test_ping_response_template_strips_distance_token_from_reply_text():
    iface = _FakeIface()
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 44.9537,
        "longitude": -93.0900,
    }
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        ping_response_template="$hops hops to $location ($distance)",
        now_unix_fn=lambda: 1710001240.0,
    )
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Saint Paul",
        "state": "Minnesota",
        "country": "United States of America",
        "distance_km": 2.2,
    }
    try:
        bot.on_receive(_base_packet("ping 9b7c"), iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    assert str(sent[0]["text"]).strip() == "3 hops to Saint Paul, Minnesota"


def test_ping_falls_back_to_known_node_hops_when_packet_hops_missing():
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
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "3 hops" in text
    assert "hop count n/a" not in text


def test_ping_keeps_hops_na_when_packet_and_node_hops_are_unavailable():
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
    packet["fromId"] = "!deadbeef"
    packet["from"] = 0xDEADBEEF
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "hop count n/a" in text


def test_ping_uses_last_known_hops_when_future_packet_loses_hop_fields():
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
    bot.on_receive(_base_packet("ping 9b7c", packet_id=2001), iface)

    # Simulate later packets that lack both packet hop fields and node cache hops_away.
    iface.nodesByNum[0x49B5DFF0].pop("hopsAway", None)
    packet = _base_packet("ping 9b7c", packet_id=2002)
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    bot.on_receive(packet, iface)

    assert len(sent) == 2
    text = str(sent[-1]["text"]).lower()
    assert "3 hops" in text
    assert "hop count n/a" not in text
    history = bot.recent_requests(limit=2)
    assert history[0]["hops"] == 3
    assert history[0]["response_hops"] == 3


def test_ping_uses_explicit_packet_hops_when_present():
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
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    packet["hops"] = 0
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "0 hops" in text
    assert "hop count n/a" not in text


def test_ping_uses_snake_case_hop_fields_when_present():
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
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    packet["hop_start"] = 7
    packet["hop_limit"] = 7
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "0 hops" in text
    assert "hop count n/a" not in text


def test_ping_uses_nested_packet_metadata_hops_when_top_level_hops_missing():
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
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    packet["metadata"] = {
        "routing": {
            "hopStart": 5,
            "hopLimit": 1,
        }
    }
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "4 hops" in text
    assert "hop count n/a" not in text


def test_ping_falls_back_to_alternate_node_hop_keys_when_packet_hops_missing():
    iface = _FakeIface()
    iface.nodesByNum[0x49B5DFF0].pop("hopsAway", None)
    iface.nodesByNum[0x49B5DFF0]["last_hops"] = 6
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
    packet.pop("hopStart", None)
    packet.pop("hopLimit", None)
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "6 hops" in text
    assert "hop count n/a" not in text


def test_ping_ignores_signal_fields_when_present():
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
    packet["rxRssi"] = -89
    packet["rxSnr"] = 9.34
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "link " not in text
    assert "3 hops" in text


def test_ping_ignores_snake_case_signal_fields_when_present():
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
    packet["rx_snr"] = -1.76
    bot.on_receive(packet, iface)

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "link " not in text
    assert "3 hops" in text


def test_ping_includes_bot_city_hint_when_local_node_has_position():
    iface = _FakeIface()
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 44.98,
        "longitude": -93.26,
    }
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
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Minneapolis",
        "state": "Minnesota",
        "country": "United States of America",
        "distance_km": 2.4,
    }
    try:
        bot.on_receive(_base_packet("ping 9b7c"), iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "bot near minneapolis, minnesota." in text


def test_ping_omits_bot_city_hint_when_local_node_position_is_unavailable():
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
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Minneapolis",
        "state": "Minnesota",
        "country": "United States of America",
        "distance_km": 2.4,
    }
    try:
        bot.on_receive(_base_packet("ping 9b7c"), iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "bot near " not in text


def test_ping_omits_bot_to_requester_distance_even_when_positions_are_known():
    iface = _FakeIface()
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 44.9778,
        "longitude": -93.2650,
    }
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
    packet["decoded"]["position"] = {
        "latitude": 44.9778,
        "longitude": -93.2650,
    }
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Minneapolis",
        "state": "Minnesota",
        "country": "United States of America",
        "distance_km": 0.8,
    }
    try:
        bot.on_receive(packet, iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "bot near minneapolis, minnesota" in text
    assert "from you" not in text


def test_ping_does_not_include_distance_from_recent_requester_node_position():
    iface = _FakeIface()
    iface.nodesByNum[0x49B5DFF0]["position"] = {
        "latitude": 44.98,
        "longitude": -93.26,
        "time": 1710001235,
    }
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 44.9778,
        "longitude": -93.2650,
    }
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
    text = str(sent[0]["text"]).lower()
    assert "from you" not in text
    assert "3 hops" in text


def test_ping_omits_bot_city_hint_when_nearest_city_is_too_far():
    iface = _FakeIface()
    iface.nodesByNum[0x02ED9B7C]["position"] = {
        "latitude": 47.10,
        "longitude": -88.57,
    }
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
    original_lookup = _bot_responder_module._nearest_city_for_coords
    _bot_responder_module._nearest_city_for_coords = lambda _lat, _lon: {
        "name": "Houghton",
        "state": "Michigan",
        "country": "United States of America",
        "distance_km": 190.0,
    }
    try:
        bot.on_receive(_base_packet("ping 9b7c"), iface)
    finally:
        _bot_responder_module._nearest_city_for_coords = original_lookup

    assert len(sent) == 1
    text = str(sent[0]["text"]).lower()
    assert "bot near " not in text


def test_public_ping_limit_handoff_and_one_hour_public_suppression():
    iface = _FakeIface()
    sent = []
    now_ref = [1710001240.0]

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: now_ref[0],
    )

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3001), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3002), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3003), iface)

    assert len(sent) == 3
    assert all(row["destination"] == "^all" for row in sent[:3])
    assert all("hops" in str(row["text"]).lower() for row in sent[:3])

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3004), iface)

    assert len(sent) == 5
    assert sent[3]["destination"] == "!49b5dff0"
    assert sent[3]["channel_index"] == 0
    assert sent[3]["reply_id"] == 3004
    assert "peer-to-peer" in str(sent[3]["text"]).lower()
    assert "1 hour" in str(sent[3]["text"]).lower()
    assert sent[4]["destination"] == "^all"
    assert sent[4]["reply_id"] == 3004
    assert sent[4]["emoji"] == "❌"
    assert str(sent[4].get("text") or "") == ""

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3005), iface)
    assert len(sent) == 5


def test_public_ping_suppression_does_not_block_direct_ping():
    iface = _FakeIface()
    sent = []
    now_ref = [1710001240.0]

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: now_ref[0],
    )

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3101), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3102), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3103), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3104), iface)
    sent_before_direct_ping = len(sent)

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3105, to_id="!02ed9b7c"), iface)

    assert len(sent) == sent_before_direct_ping + 1
    assert sent[-1]["destination"] == "!49b5dff0"
    assert "hops" in str(sent[-1]["text"]).lower()


def test_public_ping_limit_resets_after_one_hour():
    iface = _FakeIface()
    sent = []
    now_ref = [1710001240.0]

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: now_ref[0],
    )

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3201), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3202), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3203), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3204), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3205), iface)
    sent_after_suppression = len(sent)

    now_ref[0] += 3601
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3206), iface)

    assert len(sent) == sent_after_suppression + 1
    assert sent[-1]["destination"] == "^all"
    assert "hops" in str(sent[-1]["text"]).lower()


def test_public_ping_handoff_direct_message_uses_incoming_channel_index():
    iface = _FakeIface()
    sent = []
    now_ref = [1710001240.0]

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: now_ref[0],
    )

    for packet_id in (3301, 3302, 3303):
        pkt = _base_packet("ping 9b7c", packet_id=packet_id)
        pkt["channel"] = 3
        bot.on_receive(pkt, iface)

    handoff_pkt = _base_packet("ping 9b7c", packet_id=3304)
    handoff_pkt["channel"] = 3
    bot.on_receive(handoff_pkt, iface)

    assert len(sent) == 5
    assert sent[3]["destination"] == "!49b5dff0"
    assert sent[3]["channel_index"] == 3
    assert sent[3]["reply_id"] == 3304
    assert sent[4]["destination"] == "^all"
    assert sent[4]["emoji"] == "❌"


def test_public_ping_handoff_falls_back_when_zork_style_direct_fails():
    iface = _FakeIface()
    sent = []
    now_ref = [1710001240.0]

    def _send_chat(**kwargs):
        destination = str(kwargs.get("destination") or "")
        text = str(kwargs.get("text") or "")
        reply_id = kwargs.get("reply_id")
        if destination.startswith("!") and text and reply_id == 3404:
            raise RuntimeError("simulated direct threaded send failure")
        sent.append(kwargs)
        return {"ok": True}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        now_unix_fn=lambda: now_ref[0],
    )

    bot.on_receive(_base_packet("ping 9b7c", packet_id=3401), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3402), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3403), iface)
    bot.on_receive(_base_packet("ping 9b7c", packet_id=3404), iface)

    # 3 public replies + reaction + fallback direct PM.
    assert len(sent) == 5
    assert sent[3]["destination"] == "!49b5dff0"
    assert sent[3]["reply_id"] is None
    assert "peer-to-peer" in str(sent[3]["text"]).lower()
    assert sent[4]["destination"] == "^all"
    assert sent[4]["emoji"] == "❌"


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
    assert enabled_names == ["ping", "joke", "zork"]
    assert settings["joke_delay_punchline_enabled"] is False


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
    assert "joke" in names
    assert "zork" in names
    assert "status" in names
    assert commands[0]["name"] == "ping"
    assert commands[1]["name"] == "joke"
    assert commands[2]["name"] == "zork"
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


def test_ping_does_not_include_request_age_when_rx_time_is_old():
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
    assert "request age" not in text
    assert "3 hops" in text


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

    assert len(sent) >= 1
    assert all(row["destination"] == "!49b5dff0" for row in sent)
    text = _joined_segment_text(sent).lower()
    assert "zork" in text
    assert "type help for list of commands" in text


def test_zork_game_can_start_from_public_chat_when_public_handoff_is_enabled():
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
        game_public_start_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2051, to_id="^all"), iface)

    assert len(sent) >= 1
    assert all(row["destination"] == "!49b5dff0" for row in sent)
    assert sent[0]["reply_id"] == 2051
    text = _joined_segment_text(sent).lower()
    assert "zork: session started." in text
    assert "west of house" in text
    assert "type help for list of commands" in text
    assert text.index("west of house") < text.index("type help for list of commands")
    history = bot.recent_requests()
    assert len(history) == 1
    assert history[0]["to_id"] == "^all"
    assert history[0]["response_to"] == "!49b5dff0"


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

    assert len(sent) >= 2
    assert sent[-1]["destination"] == "!49b5dff0"
    start_text = _joined_segment_text(sent[:-1]).lower()
    look_text = str(sent[-1]["text"]).lower()
    assert "type help for list of commands" in start_text
    assert "type help for list of commands" not in look_text
    assert "west of house" in look_text
    history = bot.recent_requests()
    assert len(history) == 2
    assert all(str(row.get("command_head") or "") == "zork" for row in history)


def test_zork_help_reply_is_split_when_transport_limit_is_exceeded():
    iface = _FakeIface()
    sent = []
    next_message_id = 5000

    def _send_chat(**kwargs):
        nonlocal next_message_id
        text = str(kwargs.get("text") or "")
        if len(text.encode("utf-8")) > 220:
            raise ValueError(
                f"Message is too long ({len(text.encode('utf-8'))} bytes). Limit is 220 bytes."
            )
        next_message_id += 1
        sent.append(kwargs)
        return {"ok": True, "message_id": next_message_id}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2301, to_id="!02ed9b7c"), iface)
    sent_before_help = len(sent)
    bot.on_receive(_base_packet("help", packet_id=2302, to_id="!02ed9b7c"), iface)

    help_segments = sent[sent_before_help:]
    assert len(help_segments) >= 2
    for index, row in enumerate(help_segments, start=1):
        part, total, body = _segment_marker(row.get("text"))
        assert part == index
        assert total == len(help_segments)
        assert body
    assert all(len(str(row["text"]).encode("utf-8")) <= 220 for row in sent)
    history = bot.recent_requests()
    assert history[0]["command"] == "help"
    assert f"1/{len(help_segments)} " in str(history[0]["response_text"])
    assert f"{len(help_segments)}/{len(help_segments)} " in str(history[0]["response_text"])


def test_zork_leaflet_reply_is_split_to_fit_transport_limit():
    iface = _FakeIface()
    sent = []
    next_message_id = 6000

    def _send_chat(**kwargs):
        nonlocal next_message_id
        text = str(kwargs.get("text") or "")
        if len(text.encode("utf-8")) > 220:
            raise ValueError(
                f"Message is too long ({len(text.encode('utf-8'))} bytes). Limit is 220 bytes."
            )
        next_message_id += 1
        sent.append(kwargs)
        return {"ok": True, "message_id": next_message_id}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2401, to_id="!02ed9b7c"), iface)
    bot.on_receive(_base_packet("open mailbox", packet_id=2402, to_id="!02ed9b7c"), iface)
    sent_before_leaflet = len(sent)
    bot.on_receive(_base_packet("read leaflet", packet_id=2403, to_id="!02ed9b7c"), iface)

    leaflet_segments = sent[sent_before_leaflet:]
    assert len(leaflet_segments) >= 2
    leaflet_joined_parts: list[str] = []
    for index, row in enumerate(leaflet_segments, start=1):
        part, total, body = _segment_marker(row.get("text"))
        assert part == index
        assert total == len(leaflet_segments)
        assert body
        leaflet_joined_parts.append(body)
        assert len(str(row.get("text") or "").encode("utf-8")) <= 220
    leaflet_joined = " ".join(leaflet_joined_parts).lower()
    assert "direct inquiries by net mail to dungeon@mit-dms." in leaflet_joined


def test_zork_leaflet_reply_reserves_headroom_for_direct_reply_metadata():
    iface = _FakeIface()
    sent = []
    next_message_id = 7000

    def _send_chat(**kwargs):
        nonlocal next_message_id
        next_message_id += 1
        sent.append(kwargs)
        return {"ok": True, "message_id": next_message_id}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        chat_max_bytes=220,
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2501, to_id="!02ed9b7c"), iface)
    bot.on_receive(_base_packet("open mailbox", packet_id=2502, to_id="!02ed9b7c"), iface)
    sent_before_leaflet = len(sent)
    bot.on_receive(_base_packet("read leaflet", packet_id=2503, to_id="!02ed9b7c"), iface)

    leaflet_segments = sent[sent_before_leaflet:]
    assert len(leaflet_segments) >= 2
    for index, row in enumerate(leaflet_segments, start=1):
        part, total, body = _segment_marker(row.get("text"))
        assert part == index
        assert total == len(leaflet_segments)
        assert body
        if index == 1:
            assert row.get("reply_id") == 2503
        else:
            assert row.get("reply_id") is None
        assert len(str(row.get("text") or "").encode("utf-8")) <= 200


def test_zork_leaflet_reply_segments_are_paced_with_configured_delay():
    iface = _FakeIface()
    sent = []
    sleep_calls: list[float] = []
    next_message_id = 7100

    def _send_chat(**kwargs):
        nonlocal next_message_id
        text = str(kwargs.get("text") or "")
        if len(text.encode("utf-8")) > 220:
            raise ValueError(
                f"Message is too long ({len(text.encode('utf-8'))} bytes). Limit is 220 bytes."
            )
        next_message_id += 1
        sent.append(kwargs)
        return {"ok": True, "message_id": next_message_id}

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        chat_max_bytes=220,
        segment_delay_seconds=0.25,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
        now_unix_fn=lambda: 1710001240.0,
    )
    bot.on_receive(_base_packet("zork", packet_id=2601, to_id="!02ed9b7c"), iface)
    bot.on_receive(_base_packet("open mailbox", packet_id=2602, to_id="!02ed9b7c"), iface)
    sent_before_leaflet = len(sent)
    sleep_before_leaflet = len(sleep_calls)
    bot.on_receive(_base_packet("read leaflet", packet_id=2603, to_id="!02ed9b7c"), iface)

    leaflet_segments = sent[sent_before_leaflet:]
    leaflet_sleep_calls = sleep_calls[sleep_before_leaflet:]
    assert len(leaflet_segments) >= 2
    assert leaflet_sleep_calls == [0.25] * (len(leaflet_segments) - 1)


def test_segmented_direct_reply_retries_unacked_parts():
    sent = []
    next_message_id = 8000

    def _send_chat(**kwargs):
        nonlocal next_message_id
        next_message_id += 1
        sent.append(kwargs)
        return {"ok": True, "message_id": next_message_id}

    def _delivery_state_lookup(message_id: int) -> str:
        if message_id == 8002:
            return "pending"
        return "acked"

    bot = MeshResponseBot(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        custom_commands={},
        game_enabled=True,
        chat_max_bytes=220,
        segment_delay_seconds=0.0,
        segment_retry_count=2,
        segment_ack_wait_seconds=0.0,
        delivery_state_lookup_fn=_delivery_state_lookup,
        sleep_fn=lambda _seconds: None,
        now_unix_fn=lambda: 1710001240.0,
    )

    segments, _payloads = bot._send_reply_text(
        text="welcome " * 120,
        destination="!49b5dff0",
        channel_index=0,
        reply_id=2701,
    )

    assert len(segments) >= 2
    assert len(sent) == len(segments) + 1
    segment_text_counts: dict[str, int] = {}
    for row in sent:
        clean = str(row.get("text") or "")
        segment_text_counts[clean] = int(segment_text_counts.get(clean) or 0) + 1
    duplicated_segments = [text for text, count in segment_text_counts.items() if count >= 2]
    assert duplicated_segments
    assert sent[0].get("reply_id") == 2701


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


def test_build_bot_from_env_can_enable_public_game_start_handoff():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_GAME_PUBLIC_START_ENABLED": "1"},
    )
    assert bot is not None
    assert bot.enabled is False
    assert bot.game_public_start_enabled is True


def test_build_bot_from_env_can_override_segment_delay():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_ENABLED": "1",
            "MESH_DASH_BOT_SEGMENT_DELAY_MS": "900",
        },
    )
    assert bot is not None
    assert bot._segment_delay_seconds == 0.9


def test_build_bot_from_env_can_override_segment_retry_controls():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_ENABLED": "1",
            "MESH_DASH_BOT_SEGMENT_RETRIES": "7",
            "MESH_DASH_BOT_SEGMENT_ACK_WAIT_MS": "1250",
        },
    )
    assert bot is not None
    assert bot._segment_retry_count == 7
    assert bot._segment_ack_wait_seconds == 1.25


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


def test_build_bot_from_env_can_hard_disable_all_incoming_commands():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_ENABLED": "1",
            "MESH_DASH_BOT_HARD_DISABLED_INCOMING_COMMANDS": "all",
        },
    )
    assert bot is not None
    settings = bot.bot_settings()
    assert settings["hard_disabled_incoming_commands"] == ["all"]

    bot.on_receive(_base_packet("test", packet_id=1901), iface)
    bot.on_receive(_base_packet("tell me a joke", packet_id=1902), iface)
    assert sent == []

    history = bot.recent_requests()
    assert len(history) == 2
    heads = {str(row.get("command_head") or "") for row in history}
    assert heads == {"ping", "joke"}
    assert all(row.get("command_enabled") is False for row in history)


def test_hard_disabled_command_cannot_be_reenabled_via_command_settings():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={
            "MESH_DASH_BOT_ENABLED": "1",
            "MESH_DASH_BOT_HARD_DISABLED_INCOMING_COMMANDS": "ping",
        },
    )
    assert bot is not None
    rows = {row["name"]: row for row in bot.bot_settings()["commands"]}
    assert rows["ping"]["enabled"] is False

    saved = bot.configure(command_settings={"ping": True})
    assert saved["ok"] is True
    rows_after = {row["name"]: row for row in bot.bot_settings()["commands"]}
    assert rows_after["ping"]["enabled"] is False


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
    assert rows["joke"]["enabled"] is True
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
        ping_response_template="Hey $sender, you are $hops hops away!",
        zork_triggers=["{nodename} zork", "{nodename} play zork"],
        joke_triggers=["tell me a joke", "make me laugh"],
        joke_lines=["line 1", "line 2"],
        joke_near_guess_lines=["close enough {punchline}"],
    )
    assert saved["ok"] is True
    assert settings_path.exists()

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["enabled"] is True
    assert payload["game_enabled"] is False
    assert payload["game_public_start_enabled"] is False
    assert payload["joke_delay_punchline_enabled"] is False
    assert payload["hard_disabled_incoming_commands"] == []
    assert payload["ping_response_template"] == "Hey $sender, you are $hops hops away!"
    assert payload["zork_triggers"] == ["{nodename} zork", "{nodename} play zork"]
    assert payload["joke_triggers"] == ["tell me a joke", "make me laugh"]
    assert payload["joke_lines"] == ["line 1", "line 2"]
    assert payload["joke_near_guess_lines"] == ["close enough {punchline}"]
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
    loaded_settings = loaded.bot_settings()
    assert loaded_settings["ping_response_template"] == "Hey $sender, you are $hops hops away!"
    assert loaded_settings["zork_triggers"] == ["{nodename} zork", "{nodename} play zork"]
    assert loaded_settings["joke_triggers"] == ["tell me a joke", "make me laugh"]
    assert loaded_settings["joke_lines"] == ["line 1", "line 2"]
    assert loaded_settings["joke_near_guess_lines"] == ["close enough {punchline}"]
    assert loaded_settings["joke_delay_punchline_enabled"] is False


def test_configure_allows_explicit_empty_joke_lines():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(joke_lines=[])
    assert saved["ok"] is True
    assert saved["joke_lines"] == []
    assert bot.bot_settings()["joke_lines"] == []


def test_configure_allows_explicit_empty_joke_near_guess_lines():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(joke_near_guess_lines=[])
    assert saved["ok"] is True
    assert saved["joke_near_guess_lines"] == []
    assert bot.bot_settings()["joke_near_guess_lines"] == []


def test_configure_allows_explicit_empty_ping_triggers():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(ping_triggers=[])
    assert saved["ok"] is True
    assert saved["ping_triggers"] == []
    assert bot.bot_settings()["ping_triggers"] == []

    bot.on_receive(_base_packet("test"), iface)
    bot.on_receive(_base_packet("can you see this?"), iface)
    assert sent == []


def test_configure_allows_explicit_empty_ping_response_template():
    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(ping_response_template="$sender:$hops")
    assert saved["ok"] is True
    assert saved["ping_response_template"] == "$sender:$hops"

    saved = bot.configure(ping_response_template="")
    assert saved["ok"] is True
    assert saved["ping_response_template"] == ""
    assert bot.bot_settings()["ping_response_template"] == ""


def test_configure_allows_explicit_empty_joke_triggers():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(joke_triggers=[])
    assert saved["ok"] is True
    assert saved["joke_triggers"] == []
    assert bot.bot_settings()["joke_triggers"] == []

    bot.on_receive(_base_packet("tell me a joke"), iface)
    assert sent == []


def test_configure_allows_explicit_empty_zork_triggers():
    iface = _FakeIface()
    sent = []

    def _send_chat(**kwargs):
        sent.append(kwargs)
        return {"ok": True}

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=_send_chat,
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_ENABLED": "1"},
    )
    assert bot is not None

    saved = bot.configure(zork_triggers=[])
    assert saved["ok"] is True
    assert saved["zork_triggers"] == []
    assert bot.bot_settings()["zork_triggers"] == []

    bot.on_receive(_base_packet("zork"), iface)
    bot.on_receive(_base_packet("play zork", packet_id=1002), iface)
    assert sent == []


def test_empty_ping_triggers_persist_and_reload_without_default_fallback(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
                "ping_triggers": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.bot_settings()["ping_triggers"] == []


def test_empty_zork_triggers_persist_and_reload_without_default_fallback(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
                "zork_triggers": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.bot_settings()["zork_triggers"] == []


def test_hard_disabled_incoming_commands_persist_and_reload(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
                "hard_disabled_incoming_commands": ["all"],
            }
        ),
        encoding="utf-8",
    )

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.bot_settings()["hard_disabled_incoming_commands"] == ["all"]


def test_empty_joke_lines_persist_and_reload_without_default_fallback(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
                "joke_lines": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.bot_settings()["joke_lines"] == []


def test_empty_joke_near_guess_lines_persist_and_reload_without_default_fallback(tmp_path):
    settings_path = tmp_path / "bot_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "log_enabled": True,
                "game_enabled": False,
                "disabled_commands": [],
                "joke_near_guess_lines": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.bot_settings()["joke_near_guess_lines"] == []


def test_public_game_start_setting_is_persisted_and_loaded_from_file(tmp_path):
    settings_path = tmp_path / "bot_settings.json"

    bot = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert bot is not None

    saved = bot.configure(
        enabled=True,
        game_enabled=True,
        game_public_start_enabled=True,
        joke_delay_punchline_enabled=True,
    )
    assert saved["ok"] is True
    assert settings_path.exists()

    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload["game_enabled"] is True
    assert payload["game_public_start_enabled"] is True
    assert payload["joke_delay_punchline_enabled"] is True

    loaded = build_mesh_response_bot_from_env(
        send_chat_fn=lambda **_kwargs: {"ok": True},
        get_local_node_id_fn=lambda _iface: "!02ed9b7c",
        env={"MESH_DASH_BOT_SETTINGS_FILE": str(settings_path)},
    )
    assert loaded is not None
    assert loaded.game_enabled is True
    assert loaded.game_public_start_enabled is True
    assert loaded.bot_settings()["joke_delay_punchline_enabled"] is True


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
