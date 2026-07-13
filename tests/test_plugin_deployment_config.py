import subprocess
from pathlib import Path


def test_container_plugin_storage_is_persistent_and_disabled_by_default() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "MESH_DASH_BOTS_ENABLE=0" in dockerfile
    assert "MESH_DASH_BOTS_DIRECTORY=/data/plugins" in dockerfile
    assert "MESH_DASH_BOTS_STATE_DB=/data/plugin-state.sqlite3" in dockerfile
    assert "MESH_DASH_BOTS_FILES_DIRECTORY=/data/plugin-files" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile

    assert 'MESH_DASH_BOTS_ENABLE: "${MESH_DASH_BOTS_ENABLE:-0}"' in compose
    assert "${MESH_DASH_BOTS_DIRECTORY:-/data/plugins}" in compose
    assert "${MESH_DASH_BOTS_STATE_DB:-/data/plugin-state.sqlite3}" in compose
    assert "${MESH_DASH_BOTS_FILES_DIRECTORY:-/data/plugin-files}" in compose
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
        "--bots-enable",
        "--no-bots-enable",
        "--bots-directory",
        "--bots-state-db",
        "--bots-files-directory",
    ):
        assert option in result.stdout

    source = script_path.read_text(encoding="utf-8")
    assert 'BOTS_DIRECTORY="$(resolve_remote_data_path "${BOTS_DIRECTORY}")"' in source
    assert 'BOTS_STATE_DB="$(resolve_remote_data_path "${BOTS_STATE_DB}")"' in source
    assert 'BOTS_FILES_DIRECTORY="$(resolve_remote_data_path "${BOTS_FILES_DIRECTORY}")"' in source
    assert "'${BOTS_STATE_DB_PARENT}'" in source
    assert "MESH_DASH_BOTS_ENABLE=${BOTS_ENABLE}" in source
    assert "MESH_DASH_BOT_ENABLE=${BOT_ENABLE_LIST}" in source
    assert "MESH_DASH_BOT_DISABLE=${BOT_DISABLE_LIST}" in source
    assert 'if [[ "${BOT_ENABLE_LIST_SET}" -eq 0 ]]' in source
    assert 'if [[ "${BOT_DISABLE_LIST_SET}" -eq 0 ]]' in source
