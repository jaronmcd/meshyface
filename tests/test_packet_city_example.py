import runpy
from types import SimpleNamespace


class _Mesh:
    def __init__(self, city="Minneapolis"):
        self.city = city

    def get_node_location(self, node_id):
        assert node_id == "!00000001"
        return {"latitude": 44.98, "longitude": -93.26}

    def nearest_city(self, latitude, longitude):
        assert (latitude, longitude) == (44.98, -93.26)
        if self.city is None:
            return None
        return {"name": self.city, "state": "Minnesota", "distance_km": 1.2}


def _context(*, city="Minneapolis"):
    entries = []
    tickers = []
    return SimpleNamespace(
        message=SimpleNamespace(sender_id="!00000001"),
        mesh=_Mesh(city),
        packet={"decoded": {"admin": {"session_passkey": "secret", "pin": "123456"}}},
        debug=lambda *values: entries.append(values),
        set_ticker=lambda ticker_id, **values: tickers.append({"id": ticker_id, **values}),
        entries=entries,
        tickers=tickers,
    )


def test_packet_city_example_emits_city_and_redacted_packet() -> None:
    module = runpy.run_path("examples/plugins/packet_city/script.py")
    handler = module["print_packet_and_city"]
    context = _context()

    handler(context)

    assert context.entries[0][0] == "packet&city:"
    payload = context.entries[0][1]
    assert payload["city"] == "Minneapolis, Minnesota (1.2 km)"
    assert payload["packet"]["decoded"]["admin"] == {
        "pin": "<redacted>",
        "session_passkey": "<redacted>",
    }


def test_packet_city_example_publishes_top_three_city_scoreboard() -> None:
    module = runpy.run_path("examples/plugins/packet_city/script.py")
    script = module["script"]
    handler = module["print_packet_and_city"]

    assert tuple(script.tickers) == ("scoreboard",)

    starting = _context()
    script.start_handler(starting)
    assert starting.tickers[-1] == {
        "id": "scoreboard",
        "value": "waiting",
        "rows": {
            "Leaders": "Waiting for city packets",
            "Counted": 0,
            "Unknown": 0,
            "Last seen": "none",
        },
        "state": "neutral",
        "detail": "Packet City top 3 · none yet · 0 unknown",
    }

    minneapolis = _context(city="Minneapolis")
    handler(minneapolis)
    assert minneapolis.tickers[-1]["value"] == "Minneapolis · 1"
    assert minneapolis.tickers[-1]["state"] == "neutral"

    saint_paul = _context(city="Saint Paul")
    handler(saint_paul)
    handler(saint_paul)
    assert saint_paul.tickers[-1]["value"] == "Saint Paul · 2"

    roseville = _context(city="Roseville")
    handler(roseville)
    handler(roseville)

    duluth = _context(city="Duluth")
    handler(duluth)

    blaine = _context(city="Blaine")
    handler(blaine)
    rows = blaine.tickers[-1]["rows"]
    assert {key: value for key, value in rows.items() if key != "Last seen"} == {
        "1. Roseville": 2,
        "2. Saint Paul": 2,
        "3. Blaine": 1,
        "Counted": 7,
        "Unknown": 0,
    }
    assert rows["Last seen"] != "none"

    unknown = _context(city=None)
    handler(unknown)
    assert unknown.tickers[-1]["rows"]["Unknown"] == 1
