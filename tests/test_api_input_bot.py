from meshdash.api_input_bot import BotSettingsRequest, parse_bot_settings_request


def test_parse_bot_settings_request_handles_valid_bool_values():
    parsed = parse_bot_settings_request(
        b'{"enabled":true,"log_enabled":"0","gameEnabled":"yes","gamePublicStartEnabled":"1","jokeDelayPunchlineEnabled":"1","command_settings":{"ping":"0","whois":true}}'
    )
    assert isinstance(parsed, BotSettingsRequest)
    assert parsed.enabled is True
    assert parsed.log_enabled is False
    assert parsed.game_enabled is True
    assert parsed.game_public_start_enabled is True
    assert parsed.joke_delay_punchline_enabled is True
    assert parsed.command_settings == {"ping": False, "whois": True}


def test_parse_bot_settings_request_handles_invalid_or_missing_values():
    parsed = parse_bot_settings_request(b'{"enabled":"maybe"}')
    assert parsed.enabled is None
    assert parsed.log_enabled is None
    assert parsed.game_enabled is None
    assert parsed.game_public_start_enabled is None
    assert parsed.joke_delay_punchline_enabled is None
    assert parsed.command_settings is None

    invalid = parse_bot_settings_request(b"{not-json}")
    assert invalid.enabled is None
    assert invalid.log_enabled is None
    assert invalid.game_enabled is None
    assert invalid.game_public_start_enabled is None
    assert invalid.joke_delay_punchline_enabled is None
    assert invalid.command_settings is None


def test_parse_bot_settings_request_parses_joke_settings_lists():
    parsed = parse_bot_settings_request(
        b'{"jokeTriggers":"tell me a joke; joke time","jokeLines":"line one\\nline two","jokeNearGuessLines":"close one\\nclose two"}'
    )
    assert parsed.joke_triggers == ["tell me a joke", "joke time"]
    assert parsed.joke_lines == ["line one", "line two"]
    assert parsed.joke_near_guess_lines == ["close one", "close two"]


def test_parse_bot_settings_request_preserves_explicit_empty_joke_lists():
    parsed = parse_bot_settings_request(
        b'{"joke_triggers":[],"joke_lines":[],"joke_near_guess_lines":[]}'
    )
    assert parsed.joke_triggers == []
    assert parsed.joke_lines == []
    assert parsed.joke_near_guess_lines == []


def test_parse_bot_settings_request_parses_zork_triggers_list():
    parsed = parse_bot_settings_request(
        b'{"zorkTriggers":"{nodename} zork; {nodename} play zork"}'
    )
    assert parsed.zork_triggers == ["{nodename} zork", "{nodename} play zork"]


def test_parse_bot_settings_request_parses_ping_response_template():
    parsed = parse_bot_settings_request(
        b'{"ping_response_template":"Hey $sender, you are $hops hops away!"}'
    )
    assert parsed.ping_response_template == "Hey $sender, you are $hops hops away!"


def test_parse_bot_settings_request_parses_pull_settings():
    parsed = parse_bot_settings_request(
        '{"pull_reel_symbols":"🍒; 🍋; ⭐; 7️⃣","pull_response_template":"🎰 $reels => $result ($prize)"}'.encode("utf-8")
    )
    assert parsed.pull_reel_symbols == ["🍒", "🍋", "⭐", "7️⃣"]
    assert parsed.pull_response_template == "🎰 $reels => $result ($prize)"


def test_parse_bot_settings_request_preserves_explicit_empty_pull_reel_symbols():
    parsed = parse_bot_settings_request(b'{"pull_reel_symbols":[]}')
    assert parsed.pull_reel_symbols == []


def test_parse_bot_settings_request_preserves_empty_ping_response_template():
    parsed = parse_bot_settings_request(b'{"ping_response_template":""}')
    assert parsed.ping_response_template == ""


def test_parse_bot_settings_request_preserves_explicit_empty_zork_triggers():
    parsed = parse_bot_settings_request(b'{"zork_triggers":[]}')
    assert parsed.zork_triggers == []


def test_parse_bot_settings_request_parses_hard_disabled_incoming_commands():
    parsed = parse_bot_settings_request(
        b'{"hardDisabledIncomingCommands":"all; ping"}'
    )
    assert parsed.hard_disabled_incoming_commands == ["all", "ping"]


def test_parse_bot_settings_request_parses_joke_delay_toggle():
    parsed = parse_bot_settings_request(
        b'{"joke_delay_punchline_enabled":"yes"}'
    )
    assert parsed.joke_delay_punchline_enabled is True
