from pathlib import Path

from meshdash.games.zork.port_tools.extract_upstream_rooms import extract_rooms_from_file


UPSTREAM_DUNG_PATH = (
    Path(__file__).resolve().parents[1]
    / "meshdash"
    / "games"
    / "zork"
    / "upstream_1977"
    / "zork-master"
    / "zork"
    / "dung.56"
)


def _room_map():
    rooms = extract_rooms_from_file(UPSTREAM_DUNG_PATH)
    return {str(room["code"]): room for room in rooms}


def test_extract_upstream_rooms_contains_house_and_kitchen() -> None:
    room_map = _room_map()

    assert len(room_map) >= 140

    whous = room_map["WHOUS"]
    assert whous["short_name"] == "West of House"
    assert "open field west of a big white house" in str(whous["long_desc"]).lower()
    assert any(exit_row.get("target") == "NHOUS" for exit_row in whous["exits"])

    kitch = room_map["KITCH"]
    assert kitch["short_name"] == "Kitchen"
    assert kitch["long_desc"] == ""
    assert any(exit_row.get("target") == "LROOM" for exit_row in kitch["exits"])
    assert "SBAG" in kitch["visible_object_codes"]


def test_extract_upstream_rooms_handles_rooms_without_literal_short_names() -> None:
    room_map = _room_map()

    vair1 = room_map["VAIR1"]
    assert vair1["short_name"] == "Volcano Core"
    assert "hundred feet above the bottom of the volcano" in str(vair1["long_desc"]).lower()


def test_extract_upstream_rooms_resolves_shared_forest_description() -> None:
    room_map = _room_map()

    fore1 = room_map["FORE1"]
    assert fore1["short_name"] == "Forest"
    assert "you are in a forest, with trees in all directions around you." in str(fore1["long_desc"]).lower()
