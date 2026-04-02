from meshdash.history_profile import (
    build_profiled_history_db_path,
    local_node_id_from_profiled_history_db_path,
    resolve_history_profile_key,
)


def test_resolve_history_profile_key_prefers_canonical_local_node_id():
    key = resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda _iface: "!A1B2C3D4",
        mesh_target_label="/dev/ttyACM0 (serial)",
    )
    assert key == "a1b2c3d4"


def test_resolve_history_profile_key_falls_back_to_mesh_target_slug():
    key = resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn=lambda _iface: "local",
        mesh_target_label="/dev/ttyACM0 (serial)",
    )
    assert key == "dev-ttyacm0-serial"


def test_resolve_history_profile_key_handles_non_callable_getter():
    key = resolve_history_profile_key(
        iface=object(),
        get_local_node_id_fn="not-callable",
        mesh_target_label="192.168.1.10:4403 (tcp)",
    )
    assert key == "192-168-1-10-4403-tcp"


def test_build_profiled_history_db_path_appends_radio_suffix():
    profiled = build_profiled_history_db_path(
        "/tmp/mesh_dashboard_history.sqlite3",
        profile_key="a1b2c3d4",
    )
    assert profiled == "/tmp/mesh_dashboard_history.radio-a1b2c3d4.sqlite3"


def test_build_profiled_history_db_path_is_idempotent_for_same_key():
    profiled = build_profiled_history_db_path(
        "/tmp/mesh_dashboard_history.radio-a1b2c3d4.sqlite3",
        profile_key="a1b2c3d4",
    )
    assert profiled == "/tmp/mesh_dashboard_history.radio-a1b2c3d4.sqlite3"


def test_build_profiled_history_db_path_skips_memory_and_uri_paths():
    assert build_profiled_history_db_path(":memory:", profile_key="a1b2c3d4") == ":memory:"
    assert (
        build_profiled_history_db_path("file::memory:", profile_key="a1b2c3d4")
        == "file::memory:"
    )
    assert (
        build_profiled_history_db_path("file:/tmp/history.sqlite3", profile_key="a1b2c3d4")
        == "file:/tmp/history.sqlite3"
    )


def test_local_node_id_from_profiled_history_db_path_reads_radio_hex_suffix():
    local_node_id = local_node_id_from_profiled_history_db_path(
        "/tmp/mesh_dashboard_history.radio-A1B2C3D4.sqlite3"
    )
    assert local_node_id == "!a1b2c3d4"


def test_local_node_id_from_profiled_history_db_path_ignores_non_node_profiles():
    assert (
        local_node_id_from_profiled_history_db_path(
            "/tmp/mesh_dashboard_history.radio-192-168-1-10-4403-tcp.sqlite3"
        )
        == ""
    )
