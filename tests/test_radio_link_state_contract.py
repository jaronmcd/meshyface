from meshdash.revision import RevisionInfo
from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_service import build_dashboard_state_typed
from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot


class _Tracker:
    def __init__(self, *, connected=None, changed_unix=0, error=None) -> None:
        self.radio_link_connected = connected
        self.radio_link_changed_unix = changed_unix
        self.radio_link_error = error

    def snapshot(self, by_id: dict[str, dict[str, object]]) -> object:
        return empty_tracker_snapshot()

    def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
        return {}

    def load_node_position_counts(self) -> dict[str, dict[str, object]]:
        return {}

    def load_node_capabilities(self) -> dict[str, dict[str, object]]:
        return {}


def _revision() -> RevisionInfo:
    return RevisionInfo(
        version="0.0.0",
        commit="test",
        label="test",
        title="test",
    )


def _state_for_tracker(tracker: _Tracker):
    return build_dashboard_state_typed(
        iface=object(),
        tracker=tracker,
        target="/dev/ttyUSB0",
        started_at=1_800_000_000,
        storage_probe_path=None,
        revision_info=_revision(),
        collect_nodes_fn=lambda iface: CollectedNodes(
            rows=[],
            full=[],
            by_id={},
            with_position_count=0,
        ),
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        get_radio_connection_status_fn=lambda iface: {
            "wifi": {"is_connected": True},
        },
    )


def test_dashboard_state_exposes_tracker_radio_link_as_single_connection_contract() -> None:
    payload = _state_for_tracker(_Tracker(connected=True, changed_unix=1234))

    assert payload.summary["radio_link"] == {
        "state": "connected",
        "connected": True,
        "changed_unix": 1234,
        "reason": None,
        "target": "/dev/ttyUSB0",
        "source": "tracker.radio_link_connected",
    }
    assert payload.summary["radio_connection"] == {"wifi": {"is_connected": True}}


def test_dashboard_state_reports_disconnected_radio_link_with_reason() -> None:
    payload = _state_for_tracker(_Tracker(connected=False, changed_unix=1250, error="serial closed"))

    assert payload.summary["radio_link"]["state"] == "disconnected"
    assert payload.summary["radio_link"]["connected"] is False
    assert payload.summary["radio_link"]["changed_unix"] == 1250
    assert payload.summary["radio_link"]["reason"] == "serial closed"
    assert "radio link lost" in str(payload.tracker_error)


def test_dashboard_state_keeps_unknown_radio_link_explicit() -> None:
    payload = _state_for_tracker(_Tracker())

    assert payload.summary["radio_link"]["state"] == "unknown"
    assert payload.summary["radio_link"]["connected"] is None
    assert payload.summary["radio_link"]["changed_unix"] is None
    assert payload.summary["radio_link"]["reason"] is None


def test_dashboard_state_coerces_radio_link_tokens_and_bad_timestamps() -> None:
    connected = _state_for_tracker(
        _Tracker(connected="online", changed_unix="not-a-unix-time", error="old error")
    )

    assert connected.summary["radio_link"]["state"] == "connected"
    assert connected.summary["radio_link"]["connected"] is True
    assert connected.summary["radio_link"]["changed_unix"] is None
    assert connected.summary["radio_link"]["reason"] is None

    disconnected = _state_for_tracker(
        _Tracker(connected="offline", changed_unix=-1, error="serial closed")
    )

    assert disconnected.summary["radio_link"]["state"] == "disconnected"
    assert disconnected.summary["radio_link"]["connected"] is False
    assert disconnected.summary["radio_link"]["changed_unix"] is None
    assert disconnected.summary["radio_link"]["reason"] == "serial closed"

    unknown = _state_for_tracker(_Tracker(connected="maybe"))

    assert unknown.summary["radio_link"]["state"] == "unknown"
    assert unknown.summary["radio_link"]["connected"] is None
