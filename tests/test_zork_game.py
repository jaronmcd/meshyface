from meshdash.games.zork import ZorkGame


def test_zork_game_happy_path_supports_classic_opening():
    game = ZorkGame()

    result = game.try_handle_message(
        text="zork",
        from_id="!49b5dff0",
        to_id="!02ed9b7c",
        local_node_id="!02ed9b7c",
        now_unix=1710001240,
        enabled=True,
    )
    assert result.handled is True
    assert result.command_name == "zork"
    assert "west of house" in str(result.reply_text).lower()
    assert game.has_active_session("!49b5dff0") is True

    expected_text_by_step = (
        ("open mailbox", "leaflet"),
        ("take leaflet", "taken"),
        ("read leaflet", "welcome to dungeon"),
        ("inventory", "leaflet"),
        ("look", "west of house"),
    )
    for step, expected in expected_text_by_step:
        result = game.try_handle_message(
            text=step,
            from_id="!49b5dff0",
            to_id="!02ed9b7c",
            local_node_id="!02ed9b7c",
            now_unix=1710001240,
            enabled=True,
        )
        assert result.handled is True
        assert result.command_name == "zork"
        assert expected in str(result.reply_text).lower()
