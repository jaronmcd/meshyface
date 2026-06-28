from types import SimpleNamespace

import meshdash.runtime_state_loader as runtime_state_loader
from meshdash.dashboard_runtime_loader_contracts import DashboardRuntimeLoaderDependencies
from meshdash.dashboard_runtime_loaders import (
    _extract_state_summary,
    _should_skip_summary_persistence,
    _to_int_or_none,
    _with_summary_persistence,
    build_dashboard_runtime_loaders_with_dependencies,
)
from meshdash.revision import RevisionInfo
from meshdash.runtime_state_contracts import StateSnapshotRuntimeDependencies
from meshdash.runtime_state_loader import build_state_snapshot_loader_with_dependencies


REVISION = RevisionInfo(version="1.0", commit="abc", label="Rev", title="Title")


def _variant_payload(name: str, uptime: int = 120) -> dict[str, object]:
    return {"variant": name, "summary": {"uptime_seconds": uptime, "packet_count": 1}}


def test_summary_persistence_wrapper_handles_full_and_lite_state_variants() -> None:
    saved: list[dict[str, object]] = []

    def base_state_fn() -> dict[str, object]:
        return _variant_payload("full")

    setattr(base_state_fn, "etag", lambda: 'W/"full"')
    setattr(base_state_fn, "raw_my_info", lambda: {"ok": True})
    setattr(base_state_fn, "_sensitive_field_names", {"token"})

    for attr_name in (
        "lite",
        "lite_chat",
        "lite_network",
        "lite_network_graph",
        "lite_network_map",
        "lite_status",
        "lite_console",
    ):
        def variant_fn(attr_name=attr_name):
            return _variant_payload(attr_name)

        setattr(variant_fn, "etag", lambda attr_name=attr_name: f'W/"{attr_name}"')
        setattr(base_state_fn, attr_name, variant_fn)

    history_store = SimpleNamespace(save_summary_metrics=lambda summary: saved.append(dict(summary)))
    wrapped = _with_summary_persistence(base_state_fn=base_state_fn, history_store=history_store)

    assert wrapped()["variant"] == "full"
    assert wrapped.etag() == 'W/"full"'  # type: ignore[attr-defined]
    assert wrapped.raw_my_info() == {"ok": True}  # type: ignore[attr-defined]
    for attr_name in (
        "lite",
        "lite_chat",
        "lite_network",
        "lite_network_graph",
        "lite_network_map",
        "lite_status",
        "lite_console",
    ):
        variant = getattr(wrapped, attr_name)
        assert variant()["variant"] == attr_name
        assert variant.etag() == f'W/"{attr_name}"'

    assert [summary["uptime_seconds"] for summary in saved] == [120] * 8

    skipped = _with_summary_persistence(
        base_state_fn=lambda: _variant_payload("startup", uptime=10),
        history_store=history_store,
    )
    assert skipped()["variant"] == "startup"
    assert len(saved) == 8

    broken = _with_summary_persistence(
        base_state_fn=lambda: {"summary": {"uptime_seconds": 120}},
        history_store=SimpleNamespace(save_summary_metrics=lambda summary: (_ for _ in ()).throw(RuntimeError("db"))),
    )
    assert broken()["summary"]["uptime_seconds"] == 120

    assert _with_summary_persistence(base_state_fn=base_state_fn, history_store=None) is base_state_fn


def test_summary_persistence_helpers_accept_mappings_and_objects() -> None:
    assert _extract_state_summary({"summary": {"uptime_seconds": 100}}) == {"uptime_seconds": 100}
    assert _extract_state_summary({"summary": "bad"}) is None
    assert _extract_state_summary(SimpleNamespace(summary={"uptime_seconds": 100})) == {"uptime_seconds": 100}
    assert _extract_state_summary(SimpleNamespace(summary=[])) is None
    assert _to_int_or_none("42") == 42
    assert _to_int_or_none(True) is None
    assert _to_int_or_none("bad") is None
    assert _should_skip_summary_persistence({"uptime_seconds": "89"}) is True
    assert _should_skip_summary_persistence({"uptime_seconds": "90"}) is False
    assert _should_skip_summary_persistence({"uptime_seconds": "bad"}) is False


def test_dashboard_runtime_loaders_wire_history_and_send_chat_dependencies() -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    tracker = SimpleNamespace()
    iface = SimpleNamespace()
    send_lock = SimpleNamespace()

    def build_state_snapshot_loader_fn(**kwargs):
        calls.append(("state", kwargs))

        def state_fn():
            return {"summary": {"uptime_seconds": 100}}

        return state_fn

    def build_node_history_loader_fn(**kwargs):
        calls.append(("node_history", kwargs))
        return lambda node_id, hours_override=None, points_override=None: {"node_id": node_id}

    def build_online_activity_loader_fn(**kwargs):
        calls.append(("online", kwargs))
        return lambda hours_override=None: {"hours": hours_override}

    def build_summary_metrics_loader_fn(**kwargs):
        calls.append(("summary", kwargs))
        return lambda hours_override=None: {"summary_hours": hours_override}

    def build_send_chat_loader_fn(**kwargs):
        calls.append(("send_chat", kwargs))
        return lambda text, **extra: {"text": text, **extra}

    history_store = SimpleNamespace(
        load_top_nodes=lambda: ["top"],
        load_link_edges=lambda: ["links"],
        load_chat_page=lambda **kwargs: ["chat"],
    )
    dependencies = DashboardRuntimeLoaderDependencies(
        iface=iface,
        tracker=tracker,
        send_lock=send_lock,
        started_at=10.0,
        target="target",
        show_secrets=False,
        history_db_path="/tmp/history.sqlite3",
        revision_info=REVISION,
        history_store=history_store,
        default_node_history_hours=24,
        default_node_history_points=100,
        send_chat_message_fn=lambda **kwargs: {"sent": kwargs},
        send_reaction_packet_fn=lambda **kwargs: {"reaction": kwargs},
        get_local_node_id_fn=lambda iface: "!local",
        default_chat_max_bytes=256,
        normalize_single_emoji_fn=lambda value: (str(value), None),
        to_int_fn=lambda value: int(value),
        utc_now_fn=lambda: "now",
        build_state_fn=lambda **kwargs: {"built": kwargs},
        build_state_snapshot_loader_fn=build_state_snapshot_loader_fn,
        build_node_history_loader_fn=build_node_history_loader_fn,
        build_online_activity_loader_fn=build_online_activity_loader_fn,
        build_summary_metrics_loader_fn=build_summary_metrics_loader_fn,
        build_send_chat_loader_fn=build_send_chat_loader_fn,
    )

    loaders = build_dashboard_runtime_loaders_with_dependencies(dependencies=dependencies)

    assert loaders.state_fn.top_nodes_fn() == ["top"]  # type: ignore[attr-defined]
    assert loaders.state_fn.link_edges_fn() == ["links"]  # type: ignore[attr-defined]
    assert loaders.state_fn.chat_history_fn() == ["chat"]  # type: ignore[attr-defined]
    assert loaders.node_history_fn("!node") == {"node_id": "!node"}
    assert loaders.online_activity_fn(12) == {"hours": 12}
    assert loaders.summary_metrics_fn(6) == {"summary_hours": 6}
    assert loaders.send_chat_fn("hello", channel_index=1) == {"text": "hello", "channel_index": 1}
    assert [name for name, _kwargs in calls] == ["state", "node_history", "online", "summary", "send_chat"]
    assert calls[0][1]["storage_probe_path"] == "/tmp/history.sqlite3"
    assert calls[-1][1]["chat_max_bytes"] == 256


def test_state_snapshot_loader_caches_variants_and_exposes_raw_debug_getters(monkeypatch) -> None:
    calls: list[str] = []
    tracker = SimpleNamespace(live_packet_count="1", radio_link_changed_unix="2", state_revision="3")
    iface = SimpleNamespace(myInfo={"token": "secret", "name": "node"}, metadata={"token": "meta-secret"})

    monkeypatch.setattr(runtime_state_loader.time, "time", lambda: 6_000.0)
    monkeypatch.setattr(
        runtime_state_loader,
        "_collect_local_state",
        lambda iface: {"token": "local-secret", "state": "ok"},
    )
    monkeypatch.setattr(
        runtime_state_loader,
        "_collect_nodes_typed",
        lambda iface: SimpleNamespace(full=[{"id": "!node", "token": "node-secret"}]),
    )

    def build_state_fn(**kwargs):
        calls.append("full")
        return {"variant": "full", "target": kwargs["target"]}

    setattr(build_state_fn, "_sensitive_field_names", ["token"])
    for attr_name in (
        "lite",
        "lite_chat",
        "lite_network",
        "lite_network_graph",
        "lite_network_map",
        "lite_status",
        "lite_console",
    ):
        setattr(
            build_state_fn,
            attr_name,
            lambda attr_name=attr_name, **kwargs: calls.append(attr_name) or {"variant": attr_name},
        )

    dependencies = StateSnapshotRuntimeDependencies(
        iface=iface,
        tracker=tracker,
        started_at=1.0,
        target="radio",
        show_secrets=False,
        storage_probe_path="/tmp/history.sqlite3",
        revision_info=REVISION,
    )
    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=build_state_fn,
    )

    assert state_fn() == {"variant": "full", "target": "radio"}
    assert state_fn() == {"variant": "full", "target": "radio"}
    assert calls == ["full"]
    assert state_fn.etag() == 'W/"full-b1000-p1-r2-s3-t100"'  # type: ignore[attr-defined]

    tracker.state_revision = "4"
    assert state_fn()["variant"] == "full"
    assert calls == ["full", "full"]
    assert state_fn.etag() == 'W/"full-b1000-p1-r2-s4-t100"'  # type: ignore[attr-defined]

    for attr_name, etag_name in (
        ("lite", "lite"),
        ("lite_chat", "lite-chat"),
        ("lite_network", "lite-network"),
        ("lite_network_graph", "lite-network-graph"),
        ("lite_network_map", "lite-network-map"),
        ("lite_status", "lite-status"),
        ("lite_console", "lite-console"),
    ):
        variant = getattr(state_fn, attr_name)
        assert variant()["variant"] == attr_name
        assert variant()["variant"] == attr_name
        assert variant.etag() == f'W/"{etag_name}-b1000-p1-r2-s4-t100"'

    assert calls == [
        "full",
        "full",
        "lite",
        "lite_chat",
        "lite_network",
        "lite_network_graph",
        "lite_network_map",
        "lite_status",
        "lite_console",
    ]
    assert state_fn.raw_my_info()["token"] == "<redacted>"  # type: ignore[attr-defined]
    assert state_fn.raw_metadata()["token"] == "<redacted>"  # type: ignore[attr-defined]
    assert state_fn.raw_local_state()["token"] == "<redacted>"  # type: ignore[attr-defined]
    assert state_fn.raw_nodes_full()[0]["token"] == "<redacted>"  # type: ignore[attr-defined]
