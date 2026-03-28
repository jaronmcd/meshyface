from meshdash.services_standalone_zork import StandaloneZorkService


def test_standalone_zork_service_starts_and_continues_session():
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0)

    started = service.play(text="zork")
    assert started["ok"] is True
    assert started["active_session"] is True
    assert started["session_id"]
    assert "West of House" in str(started["reply_text"])

    followup = service.play(text="look", session_id=started["session_id"])
    assert followup["ok"] is True
    assert followup["active_session"] is True
    assert followup["session_id"] == started["session_id"]
    assert "West of House" in str(followup["reply_text"])


def test_first_move_west_shows_full_forest_description() -> None:
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0)

    started = service.play(text="zork")
    moved = service.play(text="west", session_id=started["session_id"])

    reply = str(moved["reply_text"]).lower()
    assert "forest, with trees in all directions around you." in reply
    assert "exits north, east, south, west." in reply


def test_standalone_zork_leaflet_reply_is_not_engine_truncated() -> None:
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0)

    started = service.play(text="zork")
    session_id = str(started["session_id"])
    service.play(text="open mailbox", session_id=session_id)
    leaflet = service.play(text="read leaflet", session_id=session_id)

    reply = str(leaflet["reply_text"] or "")
    assert len(reply.encode("utf-8")) > 220
    assert "Direct inquiries by Net mail to DUNGEON@MIT-DMS." in reply


def test_standalone_zork_service_requires_start_before_followup():
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0)

    response = service.play(text="look", session_id="deadbeef")

    assert response["ok"] is False
    assert response["active_session"] is False
    assert "Send 'zork' to start" in str(response["error"])


def test_standalone_zork_service_quit_ends_session():
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0)
    started = service.play(text="zork")

    ended = service.play(text="quit", session_id=started["session_id"])

    assert ended["ok"] is True
    assert ended["active_session"] is False
    assert "session ended" in str(ended["reply_text"]).lower()


def test_standalone_zork_service_rejects_new_sessions_when_at_capacity():
    service = StandaloneZorkService(now_unix_fn=lambda: 1710001240.0, max_sessions=1)

    first = service.play(text="zork", session_id="alpha")
    assert first["ok"] is True
    assert first["active_session"] is True

    second = service.play(text="zork", session_id="bravo")
    assert second["ok"] is False
    assert second["active_session"] is False
    assert "capacity" in str(second["error"]).lower()

    followup = service.play(text="look", session_id="alpha")
    assert followup["ok"] is True
    assert followup["active_session"] is True
