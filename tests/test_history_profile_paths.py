from meshdash.history_profile import (
    build_profiled_history_db_path,
    build_shared_history_db_path,
    local_node_id_from_profiled_history_db_path,
    resolve_history_local_node_id,
    resolve_history_profile_key,
)


def test_history_profile_paths_handle_shared_memory_uri_and_profiled_files() -> None:
    assert build_shared_history_db_path("  /tmp/history.sqlite3  ") == "/tmp/history.sqlite3"
    assert build_profiled_history_db_path("", profile_key="!abcdef12") == ""
    assert build_profiled_history_db_path(":memory:", profile_key="!abcdef12") == ":memory:"
    assert build_profiled_history_db_path("file:history?mode=memory", profile_key="!abcdef12") == "file:history?mode=memory"
    assert build_profiled_history_db_path("history.sqlite3?mode=memory", profile_key="!abcdef12") == (
        "history.sqlite3?mode=memory"
    )
    assert build_profiled_history_db_path("/tmp/history.sqlite3", profile_key="!ABCDEF12") == (
        "/tmp/history.radio-abcdef12.sqlite3"
    )
    assert build_profiled_history_db_path("/tmp/history.radio-abcdef12.sqlite3", profile_key="!ABCDEF12") == (
        "/tmp/history.radio-abcdef12.sqlite3"
    )
    assert build_profiled_history_db_path("/tmp/history", profile_key="Demo Target") == "/tmp/history.radio-demo-target"


def test_local_node_id_from_profiled_history_db_path_extracts_canonical_radio_ids() -> None:
    assert local_node_id_from_profiled_history_db_path("") == ""
    assert local_node_id_from_profiled_history_db_path(":memory:") == ""
    assert local_node_id_from_profiled_history_db_path("/tmp/history.sqlite3") == ""
    assert local_node_id_from_profiled_history_db_path("/tmp/history.radio-abcdef12.sqlite3") == "!abcdef12"
    assert local_node_id_from_profiled_history_db_path("/tmp/history.radio-demo-target.sqlite3") == ""
    assert local_node_id_from_profiled_history_db_path("/tmp/history.radio-.sqlite3") == ""


def test_resolve_history_local_node_id_returns_canonical_id_or_empty() -> None:
    assert resolve_history_local_node_id(
        iface=object(),
        get_local_node_id_fn=lambda iface: "!ABCDEF12",
    ) == "!abcdef12"
    assert resolve_history_local_node_id(iface=object(), get_local_node_id_fn=None) == ""
    assert resolve_history_local_node_id(
        iface=object(),
        get_local_node_id_fn=lambda iface: "local",
        wait_for_id_seconds=0,
    ) == ""
    assert resolve_history_local_node_id(
        iface=object(),
        get_local_node_id_fn=lambda iface: (_ for _ in ()).throw(RuntimeError("not ready")),
        wait_for_id_seconds=0,
    ) == ""

    values = iter(["", "!ABCDEF12"])
    now_values = iter([0.0, 0.1])
    sleeps: list[float] = []
    assert resolve_history_local_node_id(
        iface=object(),
        get_local_node_id_fn=lambda iface: next(values),
        wait_for_id_seconds=1.0,
        poll_interval_seconds=0.1,
        now_unix_fn=lambda: next(now_values),
        sleep_fn=sleeps.append,
    ) == "!abcdef12"
    assert sleeps == [0.1]
    assert resolve_history_local_node_id(
        iface=object(),
        get_local_node_id_fn=lambda iface: "",
        wait_for_id_seconds=1.0,
        now_unix_fn=iter([0.0, 2.0]).__next__,
        sleep_fn=lambda seconds: None,
    ) == ""


def test_resolve_history_profile_key_waits_for_local_id_then_falls_back_to_target_label() -> None:
    values = iter(["local", "!ABCDEF12"])
    now_values = iter([0.0, 0.1, 0.2])
    sleeps: list[float] = []

    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda iface: next(values),
        mesh_target_label="Fallback Target",
        wait_for_id_seconds=1.0,
        poll_interval_seconds=0.1,
        now_unix_fn=lambda: next(now_values),
        sleep_fn=sleeps.append,
    ) == "abcdef12"
    assert sleeps == [0.1]

    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda iface: "",
        mesh_target_label="Fallback Target",
        wait_for_id_seconds=0,
    ) == "fallback-target"
    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda iface: "Demo Radio",
        mesh_target_label="Fallback Target",
        wait_for_id_seconds=0,
    ) == "demo-radio"
    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda iface: "",
        mesh_target_label="Fallback Target",
        wait_for_id_seconds=1.0,
        now_unix_fn=iter([0.0, 2.0]).__next__,
        sleep_fn=lambda seconds: None,
    ) == "fallback-target"
    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=None,
        mesh_target_label="",
        wait_for_id_seconds=0,
    ) == "unknown"
    assert resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda iface: (_ for _ in ()).throw(RuntimeError("not ready")),
        mesh_target_label="Broadcast",
        wait_for_id_seconds=0,
    ) == "broadcast"
