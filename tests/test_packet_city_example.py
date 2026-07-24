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


def _context(*, city="Minneapolis", packet=None):
    entries = []
    tickers = []
    return SimpleNamespace(
        message=SimpleNamespace(sender_id="!00000001"),
        mesh=_Mesh(city),
        packet=packet or {"decoded": {"portnum": "ADMIN_APP"}},
        debug=lambda *values: entries.append(values),
        set_ticker=lambda ticker_id, **values: tickers.append({"id": ticker_id, **values}),
        entries=entries,
        tickers=tickers,
    )


def test_packet_city_example_emits_city_packet_summary() -> None:
    module = runpy.run_path("mesh_dashboard_plugins/packet_city/script.py")
    handler = module["print_packet_and_city"]
    context = _context()

    handler(context)

    assert context.entries[0][0] == "packet_city"
    payload = context.entries[0][1]
    assert payload == {"city": "Minneapolis, Minnesota (1.2 km)"}


def test_packet_city_example_publishes_top_three_city_scoreboard() -> None:
    module = runpy.run_path("mesh_dashboard_plugins/packet_city/script.py")
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
            "Packets": 0,
        },
        "state": "neutral",
        "detail": "Packet City top cities · none yet · no city 0 · seen none",
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
    assert {key: value for key, value in rows.items() if key != "Seen"} == {
        "1. Roseville": 2,
        "2. Saint Paul": 2,
        "3. Blaine": 1,
        "Other": 2,
        "Packets": 7,
    }
    assert rows["Seen"] != "none"
    assert "other Duluth 1, Minneapolis 1" in blaine.tickers[-1]["detail"]

    unknown = _context(city=None)
    handler(unknown)
    assert unknown.tickers[-1]["rows"]["No city"] == 1
    assert unknown.tickers[-1]["rows"]["Packets"] == 8


def test_packet_city_example_counts_no_city_packets_in_total() -> None:
    module = runpy.run_path("mesh_dashboard_plugins/packet_city/script.py")
    handler = module["print_packet_and_city"]

    handler(_context(city="Saint Paul"))
    handler(_context(city="Saint Paul"))
    handler(_context(city=None))

    context = _context(city="Bloomington")
    handler(context)
    rows = context.tickers[-1]["rows"]

    assert rows["1. Saint Paul"] == 2
    assert rows["2. Bloomington"] == 1
    assert rows["Packets"] == 4
    assert rows["No city"] == 1
    assert context.tickers[-1]["value"] == "Saint Paul · 2"
