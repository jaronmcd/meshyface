from types import SimpleNamespace

import pytest

from meshdash.api_input_radio import RadioSettingsRequest
from meshdash.services_radio_settings import apply_radio_settings


class _FakeEnumValue:
    def __init__(self, number: int) -> None:
        self.number = number


class _FakeEnum:
    values_by_name = {
        "US": _FakeEnumValue(1),
        "EU_868": _FakeEnumValue(2),
    }


class _FakeField:
    LABEL_REPEATED = 3

    TYPE_DOUBLE = 1
    TYPE_FLOAT = 2
    TYPE_INT64 = 3
    TYPE_UINT64 = 4
    TYPE_INT32 = 5
    TYPE_FIXED32 = 7
    TYPE_BOOL = 8
    TYPE_STRING = 9
    TYPE_MESSAGE = 11
    TYPE_UINT32 = 13
    TYPE_ENUM = 14
    TYPE_SFIXED32 = 15
    TYPE_SFIXED64 = 16
    TYPE_SINT32 = 17
    TYPE_SINT64 = 18
    TYPE_FIXED64 = 6

    def __init__(self, *, field_type: int, label: int | None = None, enum_type: object | None = None) -> None:
        self.type = field_type
        self.label = label
        self.enum_type = enum_type


class _FakeDescriptor:
    def __init__(self, fields_by_name: dict[str, _FakeField]) -> None:
        self.fields_by_name = fields_by_name


class _NestedConfig:
    DESCRIPTOR = _FakeDescriptor(
        {
            "threshold": _FakeField(field_type=_FakeField.TYPE_INT32),
            "label": _FakeField(field_type=_FakeField.TYPE_STRING),
        }
    )

    def __init__(self) -> None:
        self.threshold = 0
        self.label = ""


class _ConfigMessage:
    DESCRIPTOR = _FakeDescriptor(
        {
            "address": _FakeField(field_type=_FakeField.TYPE_STRING),
            "channels": _FakeField(field_type=_FakeField.TYPE_STRING, label=_FakeField.LABEL_REPEATED),
            "enabled": _FakeField(field_type=_FakeField.TYPE_BOOL),
            "frequency_offset": _FakeField(field_type=_FakeField.TYPE_DOUBLE),
            "hop_limit": _FakeField(field_type=_FakeField.TYPE_INT32),
            "nested": _FakeField(field_type=_FakeField.TYPE_MESSAGE),
            "region": _FakeField(field_type=_FakeField.TYPE_ENUM, enum_type=_FakeEnum()),
        }
    )

    def __init__(self) -> None:
        self.address = ""
        self.channels: list[object] = []
        self.enabled = False
        self.frequency_offset = 0.0
        self.hop_limit = 0
        self.nested = _NestedConfig()
        self.region = 0


class _FakeNode:
    def __init__(self) -> None:
        self.localConfig = SimpleNamespace(lora=_ConfigMessage(), device=_ConfigMessage())
        self.moduleConfig = SimpleNamespace(mqtt=_ConfigMessage())
        self.nodeNum = 0x01020304
        self.user = {
            "id": "!01020304",
            "shortName": "OLD",
            "longName": "Old Node",
        }
        self.write_calls: list[str] = []
        self.set_owner_calls: list[dict[str, object]] = []
        self.set_time_calls: list[int] = []
        self.factory_reset_calls: list[object] = []
        self.fixed_position_calls: list[tuple[float, float, int]] = []
        self.clear_fixed_position_calls = 0
        self.reset_nodedb_calls = 0
        self.transactions: list[str] = []

    def beginSettingsTransaction(self) -> None:  # noqa: N802
        self.transactions.append("begin")

    def commitSettingsTransaction(self) -> None:  # noqa: N802
        self.transactions.append("commit")

    def writeConfig(self, section: str) -> None:  # noqa: N802
        self.write_calls.append(section)

    def setOwner(self, **kwargs: object) -> None:  # noqa: N802
        self.set_owner_calls.append(dict(kwargs))

    def setTime(self, time_sec: int = 0) -> None:  # noqa: N802
        self.set_time_calls.append(int(time_sec))

    def factoryReset(self, full: bool = False) -> None:  # noqa: N802
        self.factory_reset_calls.append(bool(full))

    def setFixedPosition(self, lat: float, lon: float, alt: int) -> None:  # noqa: N802
        self.fixed_position_calls.append((lat, lon, alt))

    def removeFixedPosition(self) -> None:  # noqa: N802
        self.clear_fixed_position_calls += 1

    def resetNodeDb(self) -> None:  # noqa: N802
        self.reset_nodedb_calls += 1


class _FallbackOwnerNode(_FakeNode):
    def setOwner(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        if kwargs:
            raise TypeError("keyword owner unsupported")
        self.set_owner_calls.append({"args": args})


class _FakeIface:
    def __init__(self, node: _FakeNode) -> None:
        self.localNode = node
        self.nodesByNum = {
            node.nodeNum: {
                "user": {
                    "id": "!01020304",
                    "shortName": "OLD",
                    "longName": "Old Node",
                }
            },
            str(node.nodeNum): {"user": {"shortName": "STR"}},
        }
        self.nodes = {
            "!01020304": {
                "num": node.nodeNum,
                "user": {
                    "id": "!01020304",
                    "shortName": "OLD",
                    "longName": "Old Node",
                },
            }
        }


class _FakeLock:
    def __init__(self) -> None:
        self.depth = 0

    def acquire(self) -> None:
        self.depth += 1

    def release(self) -> None:
        self.depth -= 1


class _FakeHistoryStore:
    def __init__(self, deleted_rows: int = 7) -> None:
        self.deleted_rows = deleted_rows
        self.reset_calls = 0

    def reset(self) -> int:
        self.reset_calls += 1
        return self.deleted_rows


class _FakeTracker:
    def __init__(self) -> None:
        self.edges = {"edge"}
        self._historical_edges = {"old-edge"}
        self.port_counts = {"chat": 1}
        self.recent_packets = [1]
        self.recent_chat = [2]
        self.live_packet_count = 12
        self.radio_link_changed_unix = 0


def _apply(request: RadioSettingsRequest, **kwargs: object) -> tuple[dict[str, object], _FakeNode, _FakeIface, _FakeLock]:
    node = kwargs.pop("node", _FakeNode())
    iface = kwargs.pop("iface", _FakeIface(node))
    lock = kwargs.pop("lock", _FakeLock())
    response = apply_radio_settings(
        request,
        iface=iface,
        send_lock=lock,
        **kwargs,
    )
    return response, node, iface, lock


def test_apply_radio_settings_writes_config_sections_and_updates_owner_cache() -> None:
    response, node, iface, lock = _apply(
        RadioSettingsRequest(
            lora={
                "region": "US",
                "hop_limit": "5",
                "enabled": "yes",
                "channels": ["primary", "secondary"],
                "unknown": "ignored",
            },
            local={
                "lora": {"frequency_offset": "1.25"},
                "device": {"address": 1234, "nested": {"threshold": "9", "label": "inner"}},
            },
            module={"mqtt": {"enabled": "on", "address": "broker.local"}},
            owner={
                "short_name": "NEW",
                "long_name": "New Node",
                "is_licensed": "yes",
                "is_unmessagable": "off",
            },
        )
    )

    assert response["ok"] is True
    assert response["write_sections"] == ["lora", "device", "mqtt"]
    assert response["ignored_fields"] == ["unknown"]
    assert response["actions_applied"] == ["set_owner"]
    assert response["applied"]["owner"]["short_name"] == "NEW"  # type: ignore[index]
    assert node.localConfig.lora.region == 1
    assert node.localConfig.lora.hop_limit == 5
    assert node.localConfig.lora.frequency_offset == 1.25
    assert node.localConfig.lora.channels == ["primary", "secondary"]
    assert node.localConfig.device.address == "1234"
    assert node.localConfig.device.nested.threshold == 9
    assert node.moduleConfig.mqtt.enabled is True
    assert node.moduleConfig.mqtt.address == "broker.local"
    assert node.write_calls == ["lora", "device", "mqtt"]
    assert node.transactions == ["begin", "commit"]
    assert node.set_owner_calls == [
        {
            "long_name": "New Node",
            "short_name": "NEW",
            "is_licensed": True,
            "is_unmessagable": False,
        }
    ]
    assert iface.nodesByNum[node.nodeNum]["user"]["shortName"] == "NEW"
    assert iface.nodes["!01020304"]["user"]["longName"] == "New Node"
    assert lock.depth == 0


def test_apply_radio_settings_runs_radio_and_dashboard_reset_actions() -> None:
    tracker = _FakeTracker()
    history_store = _FakeHistoryStore(deleted_rows=11)

    response, node, iface, _lock = _apply(
        RadioSettingsRequest(
            fixed_position={"latitude": "44.98", "longitude": "-93.26", "altitude": "251"},
            time_sync={"enabled": True, "server": "time.example", "timezone": "UTC", "timeout_ms": 1200},
            actions={
                "reset_nodedb": True,
                "reset_dashboard_db": True,
                "set_time": True,
                "regenerate_node_id": True,
                "set_fixed_position": True,
            },
        ),
        history_store=history_store,
        tracker=tracker,
        resolve_time_sync_fn=lambda **kwargs: {"ok": True, "applied_unix": 1234567890, "kwargs": kwargs},
    )

    assert response["ok"] is True
    assert response["actions_applied"] == [
        "reset_nodedb",
        "reset_dashboard_db",
        "set_time",
        "regenerate_node_id",
        "set_fixed_position",
    ]
    assert response["deleted_history_rows"] == 11
    assert response["reboot_expected"] is True
    assert node.set_time_calls == [1234567890]
    assert node.factory_reset_calls == [True]
    assert node.fixed_position_calls == [(44.98, -93.26, 251)]
    assert node.reset_nodedb_calls == 1
    assert history_store.reset_calls == 1
    assert iface.nodesByNum == {}
    assert iface.nodes == {}
    assert tracker.edges == set()
    assert tracker._historical_edges == set()
    assert tracker.port_counts == {}
    assert tracker.recent_packets == []
    assert tracker.recent_chat == []
    assert tracker.live_packet_count == 0
    assert tracker.radio_link_changed_unix > 0


def test_apply_radio_settings_uses_legacy_host_clock_time_sync() -> None:
    response, node, _iface, _lock = _apply(
        RadioSettingsRequest(actions={"set_time": True}),
        resolve_time_sync_fn=lambda **kwargs: {"ok": True, "applied_unix": 999, "kwargs": kwargs},
    )

    assert response["ok"] is True
    assert node.set_time_calls == [0]
    assert response["time_sync"]["kwargs"]["use_time_server"] is False  # type: ignore[index]
    assert response["time_sync"]["kwargs"]["server"] == "pool.ntp.org"  # type: ignore[index]


def test_apply_radio_settings_falls_back_for_older_set_owner_signature() -> None:
    node = _FallbackOwnerNode()

    response, node, _iface, _lock = _apply(
        RadioSettingsRequest(owner={"short_name": "FALL", "long_name": "Fallback", "is_licensed": True}),
        node=node,
    )

    assert response["ok"] is True
    assert node.set_owner_calls == [{"args": ("Fallback", "FALL", True)}]


@pytest.mark.parametrize(
    ("radio_request", "error"),
    [
            (
                RadioSettingsRequest(
                    fixed_position={"lat": 1, "lon": 2},
                    actions={"set_fixed_position": True, "clear_fixed_position": True},
                ),
                "Cannot set and clear fixed position in one request",
            ),
        (
            RadioSettingsRequest(fixed_position={"lat": True, "lon": 2}, actions={"set_fixed_position": True}),
            "Invalid fixed position: Latitude/longitude/altitude must be numeric values",
        ),
        (
            RadioSettingsRequest(fixed_position={"lat": 91, "lon": 2}, actions={"set_fixed_position": True}),
            "Invalid fixed position: Latitude must be between -90 and 90",
        ),
        (
            RadioSettingsRequest(),
            "No settings/actions provided",
        ),
    ],
)
def test_apply_radio_settings_rejects_invalid_requests_before_hardware_calls(
    radio_request: RadioSettingsRequest,
    error: str,
) -> None:
    response, node, _iface, _lock = _apply(radio_request)

    assert response["ok"] is False
    assert response["error"] == error
    assert node.write_calls == []
    assert node.set_time_calls == []


def test_apply_radio_settings_reports_no_valid_fields_after_unknown_updates() -> None:
    response, node, _iface, _lock = _apply(RadioSettingsRequest(lora={"not_a_field": 1}))

    assert response == {
        "ok": False,
        "error": "No valid fields/actions to apply",
        "ignored_fields": ["not_a_field"],
    }
    assert node.write_calls == []


def test_apply_radio_settings_reports_missing_radio_capabilities() -> None:
    node = _FakeNode()
    delattr(node, "localConfig")

    response, _node, _iface, _lock = _apply(RadioSettingsRequest(lora={"hop_limit": 3}), node=node)

    assert response == {"ok": False, "error": "Local config is not available"}


@pytest.mark.parametrize(
    ("radio_request", "kwargs", "error"),
    [
        (
            RadioSettingsRequest(actions={"set_time": True}),
            {"resolve_time_sync_fn": lambda **_kwargs: {"ok": False, "error": "ntp failed"}},
            "Time sync failed: ntp failed",
        ),
        (
            RadioSettingsRequest(actions={"set_time": True}, time_sync={"enabled": True}),
            {"resolve_time_sync_fn": lambda **_kwargs: {"ok": True, "applied_unix": 0}},
            "Time sync failed: invalid server time returned",
        ),
        (
            RadioSettingsRequest(actions={"reset_dashboard_db": True}),
            {},
            "Dashboard history reset failed: Dashboard history is not enabled",
        ),
    ],
)
def test_apply_radio_settings_reports_action_failures(
    radio_request: RadioSettingsRequest,
    kwargs: dict[str, object],
    error: str,
) -> None:
    response, _node, _iface, _lock = _apply(radio_request, **kwargs)

    assert response["ok"] is False
    assert response["error"] == error


def test_apply_radio_settings_reports_write_exceptions_with_context() -> None:
    class _BadWriteNode(_FakeNode):
        def writeConfig(self, section: str) -> None:  # noqa: N802
            raise RuntimeError(f"bad write {section}")

    response, _node, _iface, _lock = _apply(
        RadioSettingsRequest(lora={"hop_limit": 4}),
        node=_BadWriteNode(),
    )

    assert response["ok"] is False
    assert response["error"] == "Write failed: bad write lora"
    assert response["applied_fields"] == ["hop_limit"]
