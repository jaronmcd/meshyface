import subprocess
from pathlib import Path


def test_container_plugin_storage_is_persistent_and_disabled_by_default() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "MESH_DASH_PLUGINS_ENABLE=0" in dockerfile
    assert "MESH_DASH_PLUGINS_DIRECTORY=/data/plugins" in dockerfile
    assert "MESH_DASH_PLUGINS_STATE_DB=/data/plugin-state.sqlite3" in dockerfile
    assert "MESH_DASH_PLUGINS_FILES_DIRECTORY=/data/plugin-files" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile

    assert 'MESH_DASH_PLUGINS_ENABLE: "${MESH_DASH_PLUGINS_ENABLE:-0}"' in compose
    assert "${MESH_DASH_PLUGINS_DIRECTORY:-/data/plugins}" in compose
    assert "${MESH_DASH_PLUGINS_STATE_DB:-/data/plugin-state.sqlite3}" in compose
    assert "${MESH_DASH_PLUGINS_FILES_DIRECTORY:-/data/plugin-files}" in compose
    assert "meshyface-data:/data" in compose


def test_systemd_deploy_exposes_and_prepares_plugin_storage_options() -> None:
    script_path = Path("scripts/deploy_meshyface.sh")
    subprocess.run(["bash", "-n", str(script_path)], check=True)
    result = subprocess.run(
        ["bash", str(script_path), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    for option in (
        "--plugins-enable",
        "--no-plugins-enable",
        "--plugins-directory",
        "--plugins-state-db",
        "--plugins-files-directory",
    ):
        assert option in result.stdout

    source = script_path.read_text(encoding="utf-8")
    assert 'PLUGINS_DIRECTORY="$(resolve_remote_data_path "${PLUGINS_DIRECTORY}")"' in source
    assert 'PLUGINS_STATE_DB="$(resolve_remote_data_path "${PLUGINS_STATE_DB}")"' in source
    assert 'PLUGINS_FILES_DIRECTORY="$(resolve_remote_data_path "${PLUGINS_FILES_DIRECTORY}")"' in source
    assert "'${PLUGINS_STATE_DB_PARENT}'" in source
    assert "MESH_DASH_PLUGINS_ENABLE=${PLUGINS_ENABLE}" in source
    assert "MESH_DASH_PLUGIN_ENABLE=${PLUGIN_ENABLE_LIST}" in source
    assert "MESH_DASH_PLUGIN_DISABLE=${PLUGIN_DISABLE_LIST}" in source
    assert 'if [[ "${PLUGIN_ENABLE_LIST_SET}" -eq 0 ]]' in source
    assert 'if [[ "${PLUGIN_DISABLE_LIST_SET}" -eq 0 ]]' in source
