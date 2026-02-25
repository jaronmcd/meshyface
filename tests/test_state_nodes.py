import types

from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_nodes import collect_local_state, collect_nodes, collect_nodes_typed


def _iface_fixture(local_node=None):
    if local_node is None:
        local_node = types.SimpleNamespace(
            localConfig={"lora": {"modem_preset": "LONG_FAST"}},
            moduleConfig={"foo": "bar"},
            channels=[{"name": "primary"}],
        )
    iface = types.SimpleNamespace(
        nodesByNum={
            2: {
                "num": 2,
                "user": {"id": "!00000002", "shortName": "B", "longName": "Bravo"},
                "deviceMetrics": {"batteryLevel": 88},
                "position": {"latitude": 44.98, "longitude": -93.26},
                "lastHeard": 200,
            },
            1: {
                "num": 1,
                "user": {"shortName": "A", "longName": "Alpha"},
                "deviceMetrics": {"batteryLevel": 77},
                "lastHeard": 100,
            },
        },
        localNode=local_node,
    )
    iface.getNode = lambda _node_id: local_node
    return iface


def test_collect_nodes_shapes_rows_and_sorts_by_last_heard():
    nodes = collect_nodes(_iface_fixture())
    assert len(nodes["rows"]) == 2
    assert nodes["rows"][0]["id"] == "!00000002"
    assert nodes["rows"][1]["id"] == "!00000001"
    assert nodes["with_position_count"] == 1


def test_collect_nodes_typed_returns_collected_nodes_contract():
    nodes = collect_nodes_typed(_iface_fixture())
    assert isinstance(nodes, CollectedNodes)
    assert len(nodes.rows) == 2
    assert nodes.rows[0]["id"] == "!00000002"
    assert nodes.rows[1]["id"] == "!00000001"
    assert nodes.with_position_count == 1


def test_collect_local_state_uses_getnode_fallback():
    local = types.SimpleNamespace(
        localConfig={"lora": {"modem_preset": "MEDIUM_FAST"}},
        moduleConfig={"foo": "bar"},
        channels=[{"name": "primary"}],
    )
    iface = _iface_fixture(local_node=None)
    iface.localNode = None
    iface.getNode = lambda _node_id: local

    state = collect_local_state(iface)
    assert state["local_config"]["lora"]["modem_preset"] == "MEDIUM_FAST"
    assert len(state["channels"]) == 1
