import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.state_local import (
    _channel_index_from_jsonable,
    _dedupe_channel_list,
    _is_empty_jsonable,
    _merge_channel_jsonable,
    _resolve_local_node_info,
    collect_local_state,
)


class _FakeChannel:
    def __init__(self, *, index: int, role: int, settings: dict[str, object] | None = None) -> None:
        self.index = index
        self.role = role
        self.settings = dict(settings or {})


class _FakeNode:
    def __init__(self) -> None:
        self.localConfig = {"lora": {"modem_preset": "MEDIUM_FAST"}}
        self.moduleConfig = {"mqtt": {"address": "mqtt.meshtastic.org"}}
        self.channels = [
            _FakeChannel(index=0, role=1, settings={"name": "", "psk": b"default"}),
            _FakeChannel(index=1, role=2, settings={"name": "Meshyface", "psk": b"secret"}),
            _FakeChannel(index=2, role=0, settings={}),
        ]
        self.nodeNum = 0x1234ABCD
        self.position = {"latitude": 44.0, "longitude": -93.0}
        self.request_channels_calls: list[int] = []
        self.wait_for_config_calls: list[str] = []

    def requestChannels(self, startingIndex: int = 0) -> None:  # noqa: N802
        self.request_channels_calls.append(startingIndex)

    def waitForConfig(self, attribute: str = "channels") -> None:  # noqa: N802
        self.wait_for_config_calls.append(attribute)


class _FakeIface:
    def __init__(self) -> None:
        self.localNode = _FakeNode()
        self.myInfo = {"my_node_num": 0x1234ABCD}
        self.nodesByNum = {
            0x1234ABCD: {
                "num": 0x1234ABCD,
                "user": {"id": "!1234abcd", "longName": "Demo Relay"},
            }
        }


def test_collect_local_state_preserves_explicit_channel_roles() -> None:
    iface = _FakeIface()

    state = collect_local_state(iface)

    assert state["channels"] == [
        {"index": 0, "role": "PRIMARY", "settings": {"name": "", "psk": "64656661756c74"}},
        {"index": 1, "role": "SECONDARY", "settings": {"name": "Meshyface", "psk": "736563726574"}},
        {"index": 2, "role": "DISABLED", "settings": {}},
    ]


def test_collect_local_state_can_refresh_channels_before_serializing() -> None:
    iface = _FakeIface()

    collect_local_state(iface, refresh_channels=True)

    assert iface.localNode.request_channels_calls == [0]
    assert iface.localNode.wait_for_config_calls == ["channels"]


def test_collect_local_state_falls_back_to_get_node_and_node_map_lookup() -> None:
    class Local:
        def __init__(self) -> None:
            self.localConfig = {}
            self.moduleConfig = {}
            self.channels = []
            self.nodeNum = "305441741"
            self.local_stats = {"uptime": 10}
            self.position = None

        def requestChannels(self) -> None:  # noqa: N802
            return None

        def waitForConfig(self, _attribute: str) -> None:  # noqa: N802
            raise RuntimeError("timeout")

    local = Local()
    iface = type("Iface", (), {})()
    iface.localNode = None
    iface.myInfo = {"myNodeNum": "305441741"}
    iface.nodesByNum = {"305441741": {"user": {"id": "!1234abcd"}, "position": {"latitude": 1}}}
    iface.nodes = {}
    iface.getNode = lambda node_id: local

    state = collect_local_state(iface, refresh_channels=True)

    assert state["local_node_num"] == 305441741
    assert state["local_node_info"]["user"]["id"] == "!1234abcd"  # type: ignore[index]
    assert state["local_stats"] == {"uptime": 10}
    assert state["local_position"] == {"latitude": 1}


def test_local_state_channel_helpers_merge_sparse_duplicates() -> None:
    assert _is_empty_jsonable(None) is True
    assert _is_empty_jsonable([]) is True
    assert _is_empty_jsonable("value") is False
    assert _channel_index_from_jsonable({"index": "2"}, fallback_index=0) == 2
    assert _channel_index_from_jsonable({"index": "-1", "role": "PRIMARY"}, fallback_index=2) == 0
    assert _channel_index_from_jsonable({"role": "primary"}, fallback_index=0) == 0
    assert _channel_index_from_jsonable({"role": "secondary"}, fallback_index=1) is None
    assert _channel_index_from_jsonable("bad", fallback_index=0) is None
    assert _merge_channel_jsonable("existing", {"name": "incoming"}, channel_index=1) == "existing"
    assert _merge_channel_jsonable("", {"name": "incoming"}, channel_index=1) == {"name": "incoming"}
    assert _merge_channel_jsonable(
        {"index": None, "settings": {"name": "", "psk": "old"}, "role": ""},
        {"settings": {"name": "mesh", "psk": "new"}, "role": "PRIMARY"},
        channel_index=3,
    ) == {"index": 3, "settings": {"name": "mesh", "psk": "old"}, "role": "PRIMARY"}

    deduped = _dedupe_channel_list(
        [
            {"index": None, "role": "PRIMARY", "settings": {"name": ""}},
            {"index": 0, "settings": {"name": "primary", "psk": "abc"}},
            {"role": "secondary", "settings": {"name": "unknown"}},
            {"role": "secondary", "settings": {"name": "other"}},
        ]
    )

    assert deduped == [
        {"index": 0, "role": "PRIMARY", "settings": {"name": "primary", "psk": "abc"}},
        {"role": "secondary", "settings": {"name": "unknown"}},
        {"role": "secondary", "settings": {"name": "other"}},
    ]


def test_resolve_local_node_info_uses_nodes_mapping_user_id_fallback() -> None:
    iface = type("Iface", (), {})()
    iface.nodesByNum = {}
    iface.nodes = {
        "!other": {"user": {"id": "!00000001"}},
        "named": {"user": {"id": "!00000002"}, "position": {"latitude": 2}},
    }

    assert _resolve_local_node_info(iface, None) is None
    assert _resolve_local_node_info(iface, 2) == {"user": {"id": "!00000002"}, "position": {"latitude": 2}}
