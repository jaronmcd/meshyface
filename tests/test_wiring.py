import types

import pytest

from meshdash.wiring import (
    DashboardRuntimeDependencies,
    build_dashboard_runtime_dependencies,
    ensure_runtime_dependencies,
)


def test_ensure_runtime_dependencies_requires_meshtastic():
    with pytest.raises(RuntimeError, match="meshtastic Python package is required"):
        ensure_runtime_dependencies(meshtastic_module=None, pub_module=object())


def test_ensure_runtime_dependencies_requires_pubsub():
    with pytest.raises(RuntimeError, match="pypubsub is required"):
        ensure_runtime_dependencies(meshtastic_module=object(), pub_module=None)


def test_build_dashboard_runtime_dependencies_wraps_injected_context():
    calls = {"state": None, "reaction": None, "local_node": None, "http": None}
    fake_pub = types.SimpleNamespace(subscribe=lambda cb, topic: None)

    def _build_state_fn(**kwargs):
        calls["state"] = kwargs
        return {"ok": True}

    def _reaction_fn(**kwargs):
        calls["reaction"] = kwargs
        return {"sent": True}

    def _local_node_fn(iface, **kwargs):
        calls["local_node"] = {"iface": iface, **kwargs}
        return "!abcd1234"

    def _http_handler_fn(**kwargs):
        calls["http"] = kwargs
        return object()

    deps = build_dashboard_runtime_dependencies(
        meshtastic_module="MESHTASTIC_MODULE",
        pub_module=fake_pub,
        mesh_target_label_fn=lambda args: "target",
        open_mesh_interface_fn=lambda args: object(),
        history_store_cls=object,
        dashboard_tracker_cls=object,
        seed_tracker_fn=lambda tracker, iface: None,
        revision_info_fn=lambda: {"label": "rev", "title": "rev"},
        build_state_fn=_build_state_fn,
        sensitive_field_names={"token", "password"},
        build_node_history_loader_fn=lambda **kwargs: (lambda **_kwargs: {}),
        build_online_activity_loader_fn=lambda **kwargs: (lambda **_kwargs: {}),
        build_summary_metrics_loader_fn=lambda **kwargs: (lambda **_kwargs: {}),
        send_chat_message_fn=lambda **kwargs: {"ok": True},
        send_emoji_reaction_packet_fn=_reaction_fn,
        mesh_pb2_module="MESH_PB2",
        portnums_pb2_module="PORTNUMS_PB2",
        get_local_node_id_fn=_local_node_fn,
        to_jsonable_fn=lambda value: value,
        normalize_single_emoji_fn=lambda value: (None, None),
        to_int_fn=lambda value: value,
        utc_now_fn=lambda: "now",
        render_html_fn=lambda **kwargs: "<html></html>",
        make_http_handler_fn=_http_handler_fn,
        default_node_history_hours=72,
        guess_lan_ipv4_fn=lambda: "192.168.1.1",
        default_chat_max_bytes=220,
    )

    assert isinstance(deps, DashboardRuntimeDependencies)
    assert deps.subscribe_fn is fake_pub.subscribe

    deps.build_state_fn(iface="iface", tracker="tracker")
    assert calls["state"]["sensitive_field_names"] == {"token", "password"}
    assert calls["state"]["iface"] == "iface"

    deps.send_reaction_packet_fn(destination_id="!abcd")
    assert calls["reaction"]["mesh_pb2_module"] == "MESH_PB2"
    assert calls["reaction"]["portnums_pb2_module"] == "PORTNUMS_PB2"
    assert calls["reaction"]["destination_id"] == "!abcd"

    node_id = deps.get_local_node_id_fn("iface")
    assert node_id == "!abcd1234"
    assert calls["local_node"]["meshtastic_module"] == "MESHTASTIC_MODULE"
    assert calls["local_node"]["iface"] == "iface"

    deps.make_http_handler_fn("<html>", lambda: {})
    assert calls["http"]["default_node_history_hours"] == 72
    assert callable(calls["http"]["to_int_fn"])

    assert deps.mesh_target_label_fn("ignored") == "target"
    assert deps.subscribe_fn is fake_pub.subscribe
