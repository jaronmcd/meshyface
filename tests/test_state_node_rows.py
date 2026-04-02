from collections.abc import Mapping

from meshdash import state_node_rows as rows_mod


class _SimpleMapping(Mapping):
    def __init__(self, values):
        self._values = dict(values)

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


def test_as_dict_handles_dict_mapping_message_and_errors(monkeypatch):
    original = {"a": 1}
    assert rows_mod._as_dict(original) is original

    mapped = _SimpleMapping({"b": 2})
    assert rows_mod._as_dict(mapped) == {"b": 2}

    class _Msg:
        pass

    monkeypatch.setattr(rows_mod, "message_to_dict", lambda _v: {"c": 3})
    assert rows_mod._as_dict(_Msg()) == {"c": 3}

    monkeypatch.setattr(
        rows_mod,
        "message_to_dict",
        lambda _v: (_ for _ in ()).throw(RuntimeError("bad")),
    )
    assert rows_mod._as_dict(_Msg()) == {}


def test_collect_nodes_typed_filters_sorts_and_counts_positions(monkeypatch):
    def _safe_items(_iface):
        return [
            (999, "skip-non-dict"),
            (
                2,
                {
                    "num": 2,
                    "user": {"shortName": "N2"},
                    "deviceMetrics": {"batteryLevel": 90},
                    "position": {"latitudeI": 449500000, "longitudeI": -932600000},
                    "lastHeard": 100,
                    "snr": 1.1,
                    "rssi": -120,
                    "hopsAway": 3,
                },
            ),
            (
                1,
                {
                    "num": 1,
                    "user": {"id": "!node0001", "shortName": "N1", "longName": "Node One"},
                    "deviceMetrics": {"voltage": 4.2},
                    "position": {"latitudeI": 449800000, "longitudeI": -932500000},
                    "lastHeard": 200,
                    "snr": 2.2,
                    "rssi": -110,
                    "hopsAway": 1,
                },
            ),
            (
                3,
                {
                    "num": 3,
                    "user": {},
                    "lastHeard": 50,
                },
            ),
        ]

    monkeypatch.setattr(rows_mod, "safe_nodes_items", _safe_items)
    collected = rows_mod.collect_nodes_typed(object())

    assert [row["id"] for row in collected.rows] == ["!node0001", "!00000002", "!00000003"]
    assert all("last_heard_epoch" not in row for row in collected.rows)
    assert collected.by_id["!node0001"]["short_name"] == "N1"
    assert collected.with_position_count == 2
    assert [item["num"] for item in collected.full] == [1, 2, 3]


def test_collect_nodes_typed_skips_when_to_jsonable_not_dict(monkeypatch):
    monkeypatch.setattr(rows_mod, "safe_nodes_items", lambda _iface: [(1, {"num": 1, "user": {"id": "!a"}})])
    monkeypatch.setattr(rows_mod, "to_jsonable", lambda _value: "not-a-dict")
    collected = rows_mod.collect_nodes_typed(object())
    assert collected.rows == []
    assert collected.full == []
    assert collected.by_id == {}


def test_collect_nodes_rows_typed_handles_coercions_and_skips(monkeypatch):
    class _PosObj:
        pass

    class _InfoMsg:
        pass

    def _safe_items(_iface):
        return [
            (100, {"num": 100, "user": {"id": "!100"}, "lastHeard": 10}),
            (101, {"num": 101, "user": {"id": "!101"}, "position": _PosObj(), "lastHeard": 20}),
            (102, _SimpleMapping({"num": 102, "user": {"shortName": "No ID"}, "lastHeard": 30})),
            (103, _InfoMsg()),
            (104, {"num": 104, "user": None, "lastHeard": 40}),
        ]

    def _message_to_dict(value):
        if isinstance(value, _PosObj):
            return {"latitudeI": 449700000, "longitudeI": -932400000}
        if isinstance(value, _InfoMsg):
            return {"num": 103, "user": {"id": "!103"}, "lastHeard": 5, "snr": {"a": 1}}
        return None

    monkeypatch.setattr(rows_mod, "safe_nodes_items", _safe_items)
    monkeypatch.setattr(rows_mod, "message_to_dict", _message_to_dict)

    collected = rows_mod.collect_nodes_rows_typed(object())
    ids = [row["id"] for row in collected.rows]
    assert ids == ["!00000068", "!00000066", "!101", "!100", "!103"]
    assert collected.full == []
    assert collected.by_id["!101"]["lat"] == 44.97
    assert collected.with_position_count == 1


def test_collect_nodes_wrapper_returns_plain_dict(monkeypatch):
    monkeypatch.setattr(
        rows_mod,
        "collect_nodes_typed",
        lambda _iface: rows_mod.CollectedNodes(rows=[{"id": "!1"}], full=[], by_id={"!1": {"id": "!1"}}, with_position_count=0),
    )
    out = rows_mod.collect_nodes(object())
    assert out["rows"][0]["id"] == "!1"
