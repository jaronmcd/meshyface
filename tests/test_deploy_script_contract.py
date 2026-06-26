from pathlib import Path


def test_deploy_helper_refuses_existing_service_layout_mismatch() -> None:
    script = Path("scripts/deploy_meshyface.sh").read_text(encoding="utf-8")

    assert "detect_existing_service_layout()" in script
    assert "guard_existing_service_layout_matches_deploy()" in script
    assert "Refusing to deploy because ${SERVICE_NAME}.service is already installed with a different runtime layout." in script
    assert "This prevents copying a new payload to one directory while systemd keeps serving another." in script
    assert "--app-dir '${DETECTED_SERVICE_APP_DIR}'" in script
    assert "--config-dir '${DETECTED_SERVICE_CONFIG_DIR}'" in script
    assert "--remote-python '${DETECTED_SERVICE_REMOTE_PYTHON}'" in script
