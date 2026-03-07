from meshdash.games.zork import ZorkGame


def test_zork_game_happy_path_reaches_victory():
    game = ZorkGame()

    handled, reply, command = game.try_handle_message(
        text="zork",
        from_id="!49b5dff0",
        to_id="!02ed9b7c",
        local_node_id="!02ed9b7c",
        now_unix=1710001240,
        enabled=True,
    )
    assert handled is True
    assert command == "zork"
    assert "trailhead" in str(reply).lower()

    for step in ("north", "take key", "west", "open gate", "north", "take beacon"):
        handled, reply, command = game.try_handle_message(
            text=step,
            from_id="!49b5dff0",
            to_id="!02ed9b7c",
            local_node_id="!02ed9b7c",
            now_unix=1710001240,
            enabled=True,
        )
        assert handled is True
        assert command == "zork"

    assert "victory" in str(reply).lower()
