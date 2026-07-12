from meshdash.games.zork.engine import ZorkGame


def test_zork_game_evicts_oldest_session_at_capacity() -> None:
    game = ZorkGame(max_sessions=2)

    game._start_session("!00000001", 100)
    game._start_session("!00000002", 200)
    game._start_session("!00000003", 300)

    assert game.active_session_count() == 2
    assert game.has_active_session("!00000001") is False
    assert game.has_active_session("!00000002") is True
    assert game.has_active_session("!00000003") is True
