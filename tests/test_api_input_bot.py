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
        b'{"jokeTriggers":"tell me a joke; joke time","jokeLines":"line one\\nline two"}'
    )
    assert parsed.joke_triggers == ["tell me a joke", "joke time"]
    assert parsed.joke_lines == ["line one", "line two"]


def test_parse_bot_settings_request_preserves_explicit_empty_joke_lists():
    parsed = parse_bot_settings_request(
        b'{"joke_triggers":[],"joke_lines":[]}'
    )
    assert parsed.joke_triggers == []
    assert parsed.joke_lines == []


def test_parse_bot_settings_request_parses_joke_delay_toggle():
    parsed = parse_bot_settings_request(
        b'{"joke_delay_punchline_enabled":"yes"}'
    )
    assert parsed.joke_delay_punchline_enabled is True
