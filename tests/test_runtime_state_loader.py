from meshdash.revision import RevisionInfo
from meshdash.runtime_state_contracts import StateSnapshotRuntimeDependencies
from meshdash import runtime_state_loader as state_loader_mod
from meshdash.runtime_state_loader import (
    build_state_snapshot_loader,
    build_state_snapshot_loader_with_dependencies,
)


class _TrackerWithRadioLinkRev:
    def __init__(self):
        self.live_packet_count = 0
        self.radio_link_changed_unix = 0


def test_build_state_snapshot_loader_with_dependencies_forwards_bound_context():
    captured = {}

    def _build_state_fn(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    dependencies = StateSnapshotRuntimeDependencies(
        iface="iface",
        tracker="tracker",
        started_at=123.0,
        target="mesh-target",
        show_secrets=False,
        storage_probe_path="/tmp/db.sqlite3",
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=_build_state_fn,
    )
    result = state_fn()

    assert result == {"ok": True}
    assert captured["iface"] == "iface"
    assert captured["tracker"] == "tracker"
    assert captured["target"] == "mesh-target"
    assert captured["storage_probe_path"] == "/tmp/db.sqlite3"
    assert isinstance(captured["revision_info"], RevisionInfo)
    assert captured["revision_info"].version == "0.1.0"


def test_build_state_snapshot_loader_with_dependencies_allows_optional_storage_probe_path():
    captured = {}

    def _build_state_fn(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    dependencies = StateSnapshotRuntimeDependencies(
        iface="iface",
        tracker="tracker",
        started_at=123.0,
        target="mesh-target",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=_build_state_fn,
    )
    result = state_fn()

    assert result == {"ok": True}
    assert captured["storage_probe_path"] is None


def test_build_state_snapshot_loader_cache_key_includes_radio_link_revision():
    tracker = _TrackerWithRadioLinkRev()
    build_calls = {"count": 0}

    def _build_state_fn(**kwargs):
        del kwargs
        build_calls["count"] += 1
        return {"ok": True, "count": build_calls["count"]}

    dependencies = StateSnapshotRuntimeDependencies(
        iface="iface",
        tracker=tracker,
        started_at=123.0,
        target="mesh-target",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=_build_state_fn,
    )

    first = state_fn()
    second = state_fn()
    assert first["count"] == 1
    assert second["count"] == 1

    tracker.radio_link_changed_unix = 1234
    third = state_fn()
    assert third["count"] == 2

    etag_fn = getattr(state_fn, "etag", None)
    assert callable(etag_fn)
    etag = str(etag_fn())
    assert "-r1234-" in etag


def test_build_state_snapshot_loader_wrapper_binds_legacy_dependencies(monkeypatch):
    seen = {}
    deps = StateSnapshotRuntimeDependencies(
        iface="iface",
        tracker="tracker",
        started_at=1.0,
        target="t",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    monkeypatch.setattr(
        state_loader_mod,
        "build_state_snapshot_runtime_dependencies_from_legacy_args",
        lambda **kwargs: (seen.update(kwargs), deps)[1],
    )
    monkeypatch.setattr(
        state_loader_mod,
        "build_state_snapshot_loader_with_dependencies",
        lambda **kwargs: (seen.update({"wrapped_called": True, "wrapped_kwargs": kwargs}), lambda: {"ok": True})[1],
    )

    state_fn = build_state_snapshot_loader(
        iface="iface",
        tracker="tracker",
        started_at=1.0,
        target="t",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=deps.revision_info,
        build_state_fn=lambda **_kwargs: {"ok": True},
    )

    assert state_fn() == {"ok": True}
    assert seen["iface"] == "iface"
    assert seen["wrapped_called"] is True
    assert seen["wrapped_kwargs"]["dependencies"] is deps


def test_build_state_snapshot_loader_with_dependencies_exposes_lite_and_raw_helpers(monkeypatch):
    class _Tracker:
        live_packet_count = "bad-int"
        radio_link_changed_unix = object()

    class _Iface:
        myInfo = {"password": "secret"}
        metadata = {"version": 1}

    lite_calls = {"count": 0}

    def _build_state_fn(**_kwargs):
        return {"kind": "full"}

    def _build_state_lite(**_kwargs):
        lite_calls["count"] += 1
        return {"kind": "lite", "n": lite_calls["count"]}

    setattr(_build_state_fn, "lite", _build_state_lite)
    setattr(_build_state_fn, "_sensitive_field_names", ["password"])

    monkeypatch.setattr(state_loader_mod, "_to_jsonable", lambda value: value)
    monkeypatch.setattr(state_loader_mod, "_collect_local_state", lambda _iface: {"local": True})
    class _Nodes:
        def __init__(self, full):
            self.full = full

    monkeypatch.setattr(
        state_loader_mod,
        "_collect_nodes_typed",
        lambda _iface: _Nodes([{"password": "secret"}]),
    )
    monkeypatch.setattr(
        state_loader_mod,
        "_redact_secrets",
        lambda value, _names: {"redacted": value},
    )

    deps = StateSnapshotRuntimeDependencies(
        iface=_Iface(),
        tracker=_Tracker(),
        started_at=2.0,
        target="mesh",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=deps,
        build_state_fn=_build_state_fn,
    )

    etag_fn = getattr(state_fn, "etag")
    assert callable(etag_fn)
    assert "-p0-r0-" in etag_fn()

    lite_fn = getattr(state_fn, "lite")
    assert callable(lite_fn)
    assert lite_fn()["kind"] == "lite"
    assert lite_fn()["kind"] == "lite"
    assert lite_calls["count"] == 1
    assert callable(getattr(lite_fn, "etag"))
    assert "lite-p0-r0" in lite_fn.etag()

    assert state_fn.raw_my_info() == {"redacted": {"password": "secret"}}
    assert state_fn.raw_metadata() == {"redacted": {"version": 1}}
    assert state_fn.raw_local_state() == {"redacted": {"local": True}}
    assert state_fn.raw_nodes_full() == {"redacted": [{"password": "secret"}]}


def test_build_state_snapshot_loader_with_dependencies_show_secrets_true_and_bad_sensitive_iterable(monkeypatch):
    class _Tracker:
        live_packet_count = 1
        radio_link_changed_unix = 2

    class _Iface:
        myInfo = {"password": "secret"}
        metadata = {"version": 1}

    class _BadIterable:
        def __iter__(self):
            raise RuntimeError("bad iterable")

    def _build_state_fn(**_kwargs):
        return {"ok": True}

    setattr(_build_state_fn, "_sensitive_field_names", _BadIterable())

    monkeypatch.setattr(state_loader_mod, "_to_jsonable", lambda value: value)
    monkeypatch.setattr(state_loader_mod, "_collect_local_state", lambda _iface: {"local": True})
    class _Nodes:
        def __init__(self, full):
            self.full = full

    monkeypatch.setattr(
        state_loader_mod,
        "_collect_nodes_typed",
        lambda _iface: _Nodes([{"id": "!1"}]),
    )
    redaction_calls = {"count": 0}
    monkeypatch.setattr(
        state_loader_mod,
        "_redact_secrets",
        lambda value, _names: (redaction_calls.__setitem__("count", redaction_calls["count"] + 1), value)[1],
    )

    deps = StateSnapshotRuntimeDependencies(
        iface=_Iface(),
        tracker=_Tracker(),
        started_at=3.0,
        target="mesh",
        show_secrets=True,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )
    state_fn = build_state_snapshot_loader_with_dependencies(dependencies=deps, build_state_fn=_build_state_fn)

    assert state_fn.raw_my_info() == {"password": "secret"}
    assert state_fn.raw_metadata() == {"version": 1}
    assert state_fn.raw_local_state() == {"local": True}
    assert state_fn.raw_nodes_full() == [{"id": "!1"}]
    assert redaction_calls["count"] == 0


def test_build_state_snapshot_loader_with_dependencies_tolerates_setattr_failures(monkeypatch):
    class _Tracker:
        live_packet_count = 0
        radio_link_changed_unix = 0

    class _Iface:
        myInfo = {}
        metadata = {}

    def _build_state_fn(**_kwargs):
        return {"ok": True}

    def _build_state_lite(**_kwargs):
        return {"ok": True, "lite": True}

    setattr(_build_state_fn, "lite", _build_state_lite)

    monkeypatch.setattr(state_loader_mod, "_to_jsonable", lambda value: value)
    monkeypatch.setattr(state_loader_mod, "_collect_local_state", lambda _iface: {})

    class _Nodes:
        def __init__(self):
            self.full = []

    monkeypatch.setattr(state_loader_mod, "_collect_nodes_typed", lambda _iface: _Nodes())

    import builtins

    original_setattr = builtins.setattr

    def _flaky_setattr(obj, name, value):
        if name in {"etag", "lite", "raw_my_info"}:
            raise RuntimeError("blocked")
        return original_setattr(obj, name, value)

    monkeypatch.setattr(builtins, "setattr", _flaky_setattr)

    deps = StateSnapshotRuntimeDependencies(
        iface=_Iface(),
        tracker=_Tracker(),
        started_at=0.0,
        target="target",
        show_secrets=False,
        storage_probe_path=None,
        revision_info=RevisionInfo(version="0.1.0", commit="abc", label="L", title="T"),
    )

    state_fn = build_state_snapshot_loader_with_dependencies(
        dependencies=deps,
        build_state_fn=_build_state_fn,
    )
    assert state_fn()["ok"] is True
