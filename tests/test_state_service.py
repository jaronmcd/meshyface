from types import MappingProxyType

from meshdash.state_payload_contracts import DashboardStatePayload
from meshdash.revision import RevisionInfo
from meshdash import state_service as state_service_mod
from meshdash.state_service import (
    build_dashboard_state,
    build_dashboard_state_lite,
    build_dashboard_state_typed,
)


class _DummyTracker:
    def __init__(self):
        self.snapshot_by_id = None

    def snapshot(self, by_id):
        self.snapshot_by_id = by_id
        return {
            "live_packet_count": 4,
            "real_edge_count": 2,
            "edges": [{"from": "!a", "to": "!b", "count": 1}],
            "port_counts": [{"portnum": "TEXT_MESSAGE_APP", "count": 3}],
            "recent_packets": [{"summary": {"packet_id": 1}, "packet": {"id": 1}}],
            "recent_chat": [{"text": "hello"}],
        }

    def load_node_saved_counts(self):
        return {
            "!a": {
                "saved_packets": 7,
                "saved_points": 3,
                "saved_last_seen": "2026-01-01 00:00:00Z",
            }
        }

    def load_node_capabilities(self):
        return {"!a": {"gps_capable": True}}


class _FailingTracker:
    def snapshot(self, by_id):
        raise RuntimeError("snapshot boom")

    def load_node_saved_counts(self):
        raise RuntimeError("saved boom")

    def load_node_capabilities(self):
        raise RuntimeError("caps boom")


def test_build_dashboard_state_builds_payload_and_redacts():
    tracker = _DummyTracker()
    observed = {}
    rows = [{"id": "!a"}]

    def _collect_nodes(_iface):
        return {
            "rows": rows,
            "full": [{"id": "!a", "info": {"x": 1}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        }

    def _apply_node_saved_counts(node_rows, saved_counts):
        observed["saved_counts_rows"] = node_rows
        observed["saved_counts"] = saved_counts
        node_rows[0]["saved_packets"] = 7

    def _collect_local_state_safe(_iface, *, collect_local_state_fn):
        observed["collect_local_state_fn"] = collect_local_state_fn
        return {"local_config": {"lora": {"modem_preset": "LONG_FAST"}}}, None

    def _build_summary_payload(**kwargs):
        observed["summary_kwargs"] = kwargs
        return {"summary_ok": True}

    def _redact_secrets(state, sensitive_names):
        observed["redact_state"] = state
        observed["sensitive_names"] = sensitive_names
        return {"redacted": True}

    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {"password": "x"}, "metadata": {"board": "x1"}})(),
        tracker=tracker,
        started_at=0.0,
        target="192.168.1.109:4403 (tcp)",
        show_secrets=False,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=_collect_nodes,
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=_collect_local_state_safe,
        modem_preset_from_local_state_fn=lambda state: "LONG_FAST",
        apply_node_saved_counts_fn=_apply_node_saved_counts,
        build_summary_payload_fn=_build_summary_payload,
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=_redact_secrets,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload == {"redacted": True}
    assert tracker.snapshot_by_id == {"!a": {"id": "!a"}}
    assert observed["saved_counts_rows"] is rows
    assert observed["saved_counts"]["!a"]["saved_packets"] == 7
    assert observed["summary_kwargs"]["target"] == "192.168.1.109:4403 (tcp)"
    assert observed["summary_kwargs"]["modem_preset"] == "LONG_FAST"
    assert observed["summary_kwargs"]["tracker_data"].live_packet_count == 4
    assert observed["redact_state"]["summary"]["saved_node_count"] == 1
    assert observed["redact_state"]["summary"]["online_node_count"] == 0
    assert observed["redact_state"]["summary_error"] is None
    assert observed["redact_state"]["nodes"][0]["saved_packets"] == 7
    assert observed["redact_state"]["history_caps"]["!a"]["gps_capable"] is True
    assert observed["redact_state"]["traffic"]["recent_chat"][0]["text"] == "hello"
    assert observed["redact_state"]["my_info_error"] is None
    assert observed["redact_state"]["metadata_error"] is None
    assert observed["redact_state"]["tracker_error"] is None
    assert observed["redact_state"]["nodes_error"] is None
    assert observed["redact_state"]["tracker_saved_counts_error"] is None
    assert observed["redact_state"]["tracker_capabilities_error"] is None
    assert observed["redact_state"]["local_node_id"] == "local"
    assert observed["sensitive_names"] == {"password"}


def test_build_dashboard_state_returns_unredacted_payload_when_show_secrets():
    tracker = _DummyTracker()
    rows = [{"id": "!a"}]
    redact_called = {"value": False}

    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {"password": "x"}, "metadata": {"board": "x1"}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": rows,
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: redact_called.__setitem__("value", True),
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["generated_at"] == "2026-02-24T00:00:00Z"
    assert payload["summary"]["summary_ok"] is True
    assert payload["summary_error"] is None
    assert payload["my_info_error"] is None
    assert payload["metadata_error"] is None
    assert redact_called["value"] is False
    assert payload["nodes_error"] is None


def test_build_dashboard_state_includes_radio_connection_summary_when_available():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        get_radio_connection_status_fn=lambda iface: {
            "wifi": {
                "is_connected": True,
                "rssi_dbm": -67,
                "ssid": "The LAN Before Time",
            }
        },
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary"]["summary_ok"] is True
    assert payload["summary"]["radio_connection"]["wifi"]["is_connected"] is True
    assert payload["summary"]["radio_connection"]["wifi"]["rssi_dbm"] == -67


def test_build_dashboard_state_handles_tracker_failures_without_crashing():
    tracker = _FailingTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {
            "live_packet_count": kwargs["tracker_data"].live_packet_count
        },
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary"]["live_packet_count"] == 0
    assert payload["tracker_error"] == "snapshot boom"
    assert payload["nodes_error"] is None
    assert payload["tracker_saved_counts_error"] == "saved boom"
    assert payload["tracker_capabilities_error"] == "caps boom"
    assert payload["history_caps"] == {}
    assert payload["traffic"]["edges"] == []
    assert payload["traffic"]["recent_packets"] == []


def test_build_dashboard_state_handles_collect_nodes_failure_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: (_ for _ in ()).throw(RuntimeError("nodes boom")),
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {
            "node_count": len(kwargs["node_rows"]),
            "nodes_with_position": kwargs["nodes_with_position"],
        },
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["nodes_error"] == "nodes boom"
    assert payload["nodes"] == []
    assert payload["nodes_full"] == []
    assert payload["summary"]["node_count"] == 0
    assert payload["summary"]["nodes_with_position"] == 0
    assert tracker.snapshot_by_id == {}


def test_build_dashboard_state_handles_to_jsonable_failures_without_crashing():
    tracker = _DummyTracker()

    def _to_jsonable(value):
        if value == "fail-me":
            raise RuntimeError("json boom")
        return value

    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": "fail-me", "metadata": "fail-me"})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=_to_jsonable,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["my_info"] is None
    assert payload["metadata"] is None
    assert payload["my_info_error"] == "json boom"
    assert payload["metadata_error"] == "json boom"
    assert payload["summary_error"] is None


def test_build_dashboard_state_handles_collect_local_state_safe_loader_failure_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: (_ for _ in ()).throw(
            RuntimeError("local safe boom")
        ),
        modem_preset_from_local_state_fn=lambda state: "LONG_FAST",
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["local_state"] == {}
    assert payload["local_state_error"] == "local safe boom"
    assert payload["summary"]["modem_preset"] == "LONG_FAST"


def test_build_dashboard_state_handles_modem_preset_extractor_failure_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: (_ for _ in ()).throw(RuntimeError("preset boom")),
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["local_state_error"] == "preset boom"
    assert payload["summary"]["modem_preset"] is None


def test_build_dashboard_state_handles_apply_node_saved_counts_failure_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: (_ for _ in ()).throw(
            RuntimeError("apply boom")
        ),
        build_summary_payload_fn=lambda **kwargs: {"node_count": len(kwargs["node_rows"])},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["tracker_saved_counts_error"] == "apply boom"
    assert payload["summary"]["node_count"] == 1
    assert payload["nodes"][0]["id"] == "!a"


def test_build_dashboard_state_handles_invalid_local_state_shape_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: (["bad"], None),
        modem_preset_from_local_state_fn=lambda state: "LONG_FAST",
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["local_state"] == {}
    assert payload["local_state_error"] == "Expected local_state mapping from collect_local_state_safe_fn"
    assert payload["summary"]["modem_preset"] == "LONG_FAST"


def test_build_dashboard_state_handles_invalid_summary_shape_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: "bad-summary",
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary_error"] == "Expected summary payload mapping from build_summary_payload_fn"
    assert payload["summary"]["target"] == "target"
    assert payload["summary"]["node_count"] == 1


def test_build_dashboard_state_handles_invalid_tracker_snapshot_shape_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {
            "live_packet_count": kwargs["tracker_data"].live_packet_count
        },
        load_tracker_snapshot_safe_fn=lambda tracker, nodes_by_id: ("bad-snapshot", None),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["tracker_error"] == "Expected TrackerSnapshot or mapping, got <class 'str'>"
    assert payload["summary"]["live_packet_count"] == 0
    assert payload["traffic"]["edges"] == []


def test_build_dashboard_state_handles_invalid_saved_counts_shape_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        load_tracker_node_saved_counts_safe_fn=lambda tracker: ("bad-saved", None),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["tracker_saved_counts_error"] == "Expected node saved counts mapping"
    assert payload["summary"]["summary_ok"] is True


def test_build_dashboard_state_handles_invalid_capabilities_shape_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        load_tracker_node_capabilities_safe_fn=lambda tracker: ("bad-caps", None),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["tracker_capabilities_error"] == "Expected node capabilities mapping"
    assert payload["history_caps"] == {}
    assert payload["summary"]["summary_ok"] is True


def test_build_dashboard_state_typed_returns_contract_payload():
    tracker = _DummyTracker()
    iface = type(
        "_Iface",
        (),
        {
            "myInfo": {"my_node_num": 1234},
            "metadata": {"board": "x1"},
            "nodesByNum": {1234: {"user": {"id": "!49b54790"}}},
        },
    )()
    payload = build_dashboard_state_typed(
        iface=iface,
        tracker=tracker,
        target="target",
        started_at=0.0,
        storage_probe_path=".",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=lambda value: value,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert isinstance(payload, DashboardStatePayload)
    assert payload.generated_at == "2026-02-24T00:00:00Z"
    assert payload.summary["summary_ok"] is True
    assert payload.summary_error is None
    assert payload.traffic.recent_chat[0]["text"] == "hello"
    assert payload.local_node_id == "!49b54790"


def test_build_dashboard_state_typed_includes_name_change_status_rows_in_recent_chat():
    class _NameChangeTracker:
        def snapshot(self, by_id):
            return {
                "live_packet_count": 4,
                "real_edge_count": 2,
                "edges": [],
                "port_counts": [],
                "recent_packets": [
                    {
                        "summary": {
                            "from": "!abcd1234",
                            "to": "^all",
                            "rx_time_unix": 250,
                            "portnum": "NODEINFO_APP",
                            "channel": 0,
                        },
                        "packet": {
                            "fromId": "!abcd1234",
                            "rxTime": 250,
                            "decoded": {
                                "portnum": "NODEINFO_APP",
                                "user": {"id": "!abcd1234", "shortName": "A", "longName": "Alpha"},
                            },
                        },
                    },
                    {
                        "summary": {
                            "from": "!abcd1234",
                            "to": "^all",
                            "rx_time_unix": 300,
                            "portnum": "NODEINFO_APP",
                            "channel": 0,
                        },
                        "packet": {
                            "fromId": "!abcd1234",
                            "rxTime": 300,
                            "decoded": {
                                "portnum": "NODEINFO_APP",
                                "user": {"id": "!abcd1234", "shortName": "B", "longName": "Beta"},
                            },
                        },
                    },
                ],
                "recent_chat": [
                    {
                        "from": "!eeff0011",
                        "to": "^all",
                        "scope": "all",
                        "text": "hello",
                        "rx_time": "1970-01-01 00:04:35Z",
                    }
                ],
            }

        def load_node_saved_counts(self):
            return {}

        def load_node_capabilities(self):
            return {}

    payload = build_dashboard_state_typed(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}, "nodesByNum": {}})(),
        tracker=_NameChangeTracker(),
        target="target",
        started_at=0.0,
        storage_probe_path=".",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!abcd1234", "long_name": "Beta"}],
            "full": [{"id": "!abcd1234", "long_name": "Beta"}],
            "by_id": {"!abcd1234": {"id": "!abcd1234", "long_name": "Beta"}},
            "with_position_count": 0,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=lambda value: value,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert [entry["text"] for entry in payload.traffic.recent_chat] == [
        "hello",
        "Alpha changed their name to Beta",
    ]
    assert payload.traffic.recent_chat[1]["kind"] == "status"
    assert payload.traffic.recent_chat[1]["status_event"] == "name_change"


def test_build_dashboard_state_handles_summary_builder_failure_without_crashing():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0", "commit": "abc"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("summary boom")),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary_error"] == "summary boom"
    assert payload["summary"]["target"] == "target"
    assert payload["summary"]["node_count"] == 1
    assert payload["summary"]["live_packet_count"] == 4


def test_build_dashboard_state_coerces_mapping_summary_payload_to_dict():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: MappingProxyType({"summary_ok": True}),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary"]["summary_ok"] is True
    assert payload["summary_error"] is None


def test_build_dashboard_state_coerces_mapping_local_state_and_preserves_error():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: (
            MappingProxyType({"local_config": {"lora": {"modem_preset": "LONG_FAST"}}}),
            "local warning",
        ),
        modem_preset_from_local_state_fn=lambda state: "LONG_FAST",
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert isinstance(payload["local_state"], dict)
    assert payload["local_state"]["local_config"]["lora"]["modem_preset"] == "LONG_FAST"
    assert payload["local_state_error"] == "local warning"
    assert payload["summary"]["modem_preset"] == "LONG_FAST"


def test_build_dashboard_state_coerces_non_mapping_nested_saved_counts_to_empty_mapping():
    tracker = _DummyTracker()
    observed = {}
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, node_saved_counts: observed.update(node_saved_counts),
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        load_tracker_node_saved_counts_safe_fn=lambda tracker: ({"!a": "bad-shape"}, None),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert observed["!a"] == {}
    assert payload["tracker_saved_counts_error"] is None


def test_build_dashboard_state_coerces_non_mapping_nested_capabilities_to_empty_mapping():
    tracker = _DummyTracker()
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        load_tracker_node_capabilities_safe_fn=lambda tracker: ({"!a": "bad-shape"}, None),
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["history_caps"]["!a"] == {}
    assert payload["tracker_capabilities_error"] is None


def test_build_dashboard_state_surfaces_tracker_radio_link_loss():
    tracker = _DummyTracker()
    tracker.radio_link_connected = False
    tracker.radio_link_changed_unix = 10
    tracker.radio_link_error = "connection lost"
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert "radio link lost" in str(payload["tracker_error"])


def test_build_dashboard_state_combines_snapshot_and_radio_link_errors():
    tracker = _FailingTracker()
    tracker.radio_link_connected = False
    tracker.radio_link_changed_unix = 10
    tracker.radio_link_error = "stream disconnected"
    payload = build_dashboard_state(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"summary_ok": True},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert "snapshot boom" in str(payload["tracker_error"])
    assert "radio link lost" in str(payload["tracker_error"])


def test_build_dashboard_state_lite_reports_modem_preset_from_iface():
    tracker = _DummyTracker()
    local_node = type("_LocalNode", (), {"localConfig": {"lora": {"modem_preset": "MEDIUM_FAST"}}})()
    iface = type("_Iface", (), {"myInfo": {}, "metadata": {}, "localNode": local_node})()

    payload = build_dashboard_state_lite(
        iface=iface,
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary"]["modem_preset"] == "MEDIUM_FAST"


def test_build_dashboard_state_lite_maps_numeric_modem_preset_enum_to_name():
    tracker = _DummyTracker()
    local_node = type("_LocalNode", (), {"localConfig": {"lora": {"modem_preset": 4}}})()
    iface = type("_Iface", (), {"myInfo": {}, "metadata": {}, "localNode": local_node})()

    payload = build_dashboard_state_lite(
        iface=iface,
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=True,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"modem_preset": kwargs["modem_preset"]},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: state,
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["summary"]["modem_preset"] == "MEDIUM_FAST"


def test_state_service_private_helpers_cover_modem_normalization_and_radio_errors(monkeypatch):
    assert state_service_mod._normalize_modem_preset(None) is None
    assert state_service_mod._normalize_modem_preset(True) is None
    assert state_service_mod._normalize_modem_preset(4) == "MEDIUM_FAST"
    assert state_service_mod._normalize_modem_preset(999.0) == "999"
    assert state_service_mod._normalize_modem_preset(float("nan")) == "nan"
    assert state_service_mod._normalize_modem_preset("+8") == "SHORT_TURBO"
    assert state_service_mod._normalize_modem_preset("   ") is None
    assert state_service_mod._normalize_modem_preset("42") == "42"
    assert state_service_mod._normalize_modem_preset("longfast") == "LONG_FAST"
    assert state_service_mod._normalize_modem_preset("MODEMPRESET_LONG_FAST") == "LONG_FAST"
    assert (
        state_service_mod._normalize_modem_preset("CONFIG_LORACONFIG_MODEMPRESET_LONG_FAST")
        == "CONFIG_LORACONFIG_MODEMPRESET_LONG_FAST"
    )
    assert state_service_mod._normalize_modem_preset("unknown preset") == "unknown preset"

    assert state_service_mod._modem_preset_from_local_config({"lora": {"modem_preset": 5}}) == "SHORT_SLOW"
    assert state_service_mod._modem_preset_from_local_config({"lora": "bad"}) is None
    assert state_service_mod._modem_preset_from_local_config("bad") is None

    class _IfaceFallback:
        localNode = None

        @staticmethod
        def getNode(_id):
            raise RuntimeError("boom")

    assert state_service_mod._modem_preset_quick_from_iface(_IfaceFallback()) is None

    class _LocalMapIface:
        localNode = {"local_config": {"lora": {"modem_preset": "2"}}}

    assert state_service_mod._modem_preset_quick_from_iface(_LocalMapIface()) == "VERY_LONG_SLOW"

    class _LocalConfigWithLoraMap:
        lora = {"modem_preset": 5}

    class _IfaceLoraMap:
        localNode = type("_Node", (), {"localConfig": _LocalConfigWithLoraMap()})()

    assert state_service_mod._modem_preset_quick_from_iface(_IfaceLoraMap()) == "SHORT_SLOW"

    class _LoraObj:
        modem_preset = 6

    class _LocalConfigWithLoraObj:
        lora = _LoraObj()

    class _IfaceLoraObj:
        localNode = type("_Node", (), {"localConfig": _LocalConfigWithLoraObj()})()

    assert state_service_mod._modem_preset_quick_from_iface(_IfaceLoraObj()) == "SHORT_FAST"

    class _LoraObjNoPreset:
        modem_preset = None

    class _LocalConfigNoPreset:
        lora = _LoraObjNoPreset()

    class _IfaceNoPreset:
        localNode = type("_Node", (), {"localConfig": _LocalConfigNoPreset()})()

    assert state_service_mod._modem_preset_quick_from_iface(_IfaceNoPreset()) is None

    class _TrackerConnected:
        radio_link_connected = True

    assert state_service_mod._tracker_radio_link_error(_TrackerConnected()) is None

    class _TrackerBadChanged:
        radio_link_connected = False
        radio_link_changed_unix = object()
        radio_link_error = "serial disconnected"

    assert "serial disconnected" in state_service_mod._tracker_radio_link_error(_TrackerBadChanged())

    class _TrackerTimeError:
        radio_link_connected = False
        radio_link_changed_unix = 42
        radio_link_error = ""

    monkeypatch.setattr(state_service_mod.time, "time", lambda: (_ for _ in ()).throw(RuntimeError("clock")))
    assert state_service_mod._tracker_radio_link_error(_TrackerTimeError()) == "radio link lost"


def test_build_dashboard_state_lite_redacts_when_show_secrets_false():
    tracker = _DummyTracker()
    captured = {}
    payload = build_dashboard_state_lite(
        iface=type("_Iface", (), {"myInfo": {}, "metadata": {}, "localNode": None})(),
        tracker=tracker,
        started_at=0.0,
        target="target",
        show_secrets=False,
        storage_probe_path=".",
        revision_info={"version": "0.1.0"},
        sensitive_field_names={"password"},
        collect_nodes_fn=lambda iface: {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        },
        collect_local_state_fn=lambda iface: {},
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        modem_preset_from_local_state_fn=lambda state: None,
        apply_node_saved_counts_fn=lambda node_rows, saved_counts: None,
        build_summary_payload_fn=lambda **kwargs: {"ok": True},
        to_jsonable_fn=lambda value: value,
        redact_secrets_fn=lambda state, names: (captured.update({"state": state}), {"redacted": True})[1],
        utc_now_fn=lambda: "2026-02-24T00:00:00Z",
    )

    assert payload["redacted"] is True
    assert captured["state"]["my_info"] is None
    assert captured["state"]["nodes_full"] == []
