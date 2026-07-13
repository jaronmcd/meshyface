import runpy
from types import SimpleNamespace


class _Mesh:
    def get_node_location(self, node_id):
        assert node_id == "!00000001"
        return {"latitude": 44.98, "longitude": -93.26}

    def nearest_city(self, latitude, longitude):
        assert (latitude, longitude) == (44.98, -93.26)
        return {"name": "Minneapolis", "state": "Minnesota", "distance_km": 1.2}


def test_packet_city_example_emits_city_and_redacted_packet() -> None:
    module = runpy.run_path("examples/plugins/packet_city/bot.py")
    handler = module["print_packet_and_city"]
    entries = []
    context = SimpleNamespace(
        message=SimpleNamespace(sender_id="!00000001"),
        mesh=_Mesh(),
        packet={"decoded": {"admin": {"session_passkey": "secret", "pin": "123456"}}},
        debug=lambda *values: entries.append(values),
    )

    handler(context)

    assert entries[0][0] == "packet&city:"
    payload = entries[0][1]
    assert payload["city"] == "Minneapolis, Minnesota (1.2 km)"
    assert payload["packet"]["decoded"]["admin"] == {
        "pin": "<redacted>",
        "session_passkey": "<redacted>",
    }
