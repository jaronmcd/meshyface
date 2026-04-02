import json

from meshdash import helpers_json as json_helpers


def test_safe_json_loads_success_and_default_paths():
    assert json_helpers.safe_json_loads('{"ok":true}', default={}) == {"ok": True}
    assert json_helpers.safe_json_loads("{bad-json}", default={"fallback": 1}) == {"fallback": 1}
    assert json_helpers.safe_json_loads(None, default={"fallback": 2}) == {"fallback": 2}  # type: ignore[arg-type]


def test_message_to_dict_and_to_jsonable_handle_protobuf_like_values(monkeypatch):
    class _FakeMessage:
        pass

    monkeypatch.setattr(json_helpers, "_protobuf_message_type", _FakeMessage)
    monkeypatch.setattr(
        json_helpers,
        "_protobuf_message_to_dict",
        lambda value, preserving_proto_field_name=True: {
            "kind": "fake",
            "preserve": preserving_proto_field_name,
            "id": id(value),
        },
    )

    msg = _FakeMessage()
    as_dict = json_helpers.message_to_dict(msg)
    assert as_dict["kind"] == "fake"
    assert as_dict["preserve"] is True
    assert json_helpers.message_to_dict("not-msg") is None

    jsonable = json_helpers.to_jsonable({"msg": msg})
    assert jsonable["msg"]["kind"] == "fake"


def test_to_jsonable_supports_primitives_containers_and_fallback_str():
    class _Custom:
        def __str__(self):
            return "custom-str"

    payload = {
        "none": None,
        "text": "ok",
        "num": 1,
        "flag": True,
        "raw": b"\x01\xff",
        "items": (1, 2),
        "set": {3, 4},
        "obj": _Custom(),
    }
    out = json_helpers.to_jsonable(payload)

    # ensure output remains json-serializable
    json.dumps(out)
    assert out["raw"] == "01ff"
    assert out["obj"] == "custom-str"
    assert sorted(out["set"]) == [3, 4]
