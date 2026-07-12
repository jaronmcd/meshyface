import argparse

import pytest

from mesh_dashboard import _validate_sideband_traffic_startup_args
from meshdash.cli import build_dashboard_parser
from meshdash.html_template import render_html


def _render_html(**overrides: object) -> str:
    kwargs: dict[str, object] = {
        "refresh_ms": 1000,
        "packet_limit": 200,
        "show_secrets": False,
        "history_enabled": True,
        "history_max_rows": 200,
        "history_retention_days": 7,
        "node_history_hours": 24,
        "node_history_max_points": 240,
        "revision_label": "test",
        "revision_title": "test",
    }
    kwargs.update(overrides)
    return render_html(**kwargs)


def _build_parser(**overrides: object) -> argparse.ArgumentParser:
    kwargs: dict[str, object] = {
        "add_mesh_connection_args_fn": _add_mesh_connection_args,
        "default_mesh_port": "/dev/ttyUSB0",
        "default_gateway_host": "",
        "default_gateway_port": 4403,
        "env_gateway_host": "",
        "env_gateway_port": None,
        "default_http_host": "127.0.0.1",
        "default_http_port": 8877,
        "default_refresh_ms": 3000,
        "default_packet_limit": 250,
        "default_reset_ticker_scale_on_restart": True,
        "default_history_db": "mesh_dashboard_history.sqlite3",
        "env_history_db": None,
        "default_history_max_rows": 1000,
        "default_history_retention_days": 7,
        "default_history_event_max_rows": 1000,
        "default_history_event_retention_days": 30,
        "default_history_rollup_retention_days": 365,
        "default_node_history_hours": 72,
        "default_node_history_max_points": 1440,
        "env_theme_presets": None,
        "env_theme_preset": None,
        "env_theme_settings_file": None,
        "default_file_transfer_enable": False,
        "default_file_transfer_auto_accept": False,
        "default_games_enable": False,
        "default_file_transfer_max_bytes": 64 * 1024,
        "env_file_transfer_enable": None,
        "env_file_transfer_auto_accept": None,
        "env_games_enable": None,
        "env_file_transfer_max_bytes": None,
        "env_accept_file_transfer_traffic_disclaimer": None,
    }
    kwargs.update(overrides)
    return build_dashboard_parser(**kwargs)


def test_render_html_omits_removed_bbs_and_bots_workspaces() -> None:
    html = _render_html()

    assert "bbsFeatureEnabled" not in html
    assert 'data-app-view="bbs"' not in html
    assert 'class="card bbs"' not in html
    assert "/api/settings/bbs" not in html
    assert "/api/bbs/host" not in html
    assert 'const gamesFeatureEnabled = !!Number(0);' in html
    assert 'data-app-view="games"' in html
    assert '<section class="card games workspace-app-shell" aria-label="Games">' in html
    assert 'data-app-view="bots"' not in html
    assert 'class="card bots"' not in html
    assert 'data-ticker-id="bots"' not in html
    assert "/api/bots/" not in html


def test_render_html_exposes_games_flag_when_enabled() -> None:
    html = _render_html(games_enabled=True)

    assert 'const gamesFeatureEnabled = !!Number(1);' in html
    assert "if (gamesFeatureEnabled) {" in html
    assert 'data-app-view="games"' in html
    assert '<section class="card games workspace-app-shell" aria-label="Games">' in html
    assert 'id="games-library-select"' in html
    assert 'fetch("/api/games/zork"' in html
    assert 'name: "zork"' in html
    assert 'data-app-view="bots"' not in html


def test_render_html_exposes_file_transfer_auto_accept_default() -> None:
    html = _render_html(
        file_transfer_enabled=True,
        file_transfer_auto_accept=True,
    )

    assert 'const fileTransferFeatureEnabled = !!Number(1);' in html
    assert 'const fileTransferAutoAcceptDefault = !!Number(1);' in html
    assert 'id="files-auto-accept-toggle"' in html
    assert "meshDashboardFileTransferAutoAcceptV1" in html
    assert "function autoAcceptInboundFileTransferIfEnabled(" in html


def test_dashboard_parser_rejects_removed_bbs_and_bot_flags() -> None:
    parser = _build_parser()

    for flag in (
        "--bbs-enable",
        "--no-bbs-enable",
        "--bots-enable",
        "--ping-bot-enable",
        "--zork-bot-enable",
    ):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args([flag])
        assert exc.value.code == 2
    assert "bot" not in parser.format_help().lower()


def test_dashboard_parser_supports_games_enable_flag_and_env_default() -> None:
    parser = _build_parser(env_games_enable="1")

    env_default_args = parser.parse_args([])
    assert env_default_args.games_enable is True

    explicit_disable_args = parser.parse_args(["--no-games-enable"])
    assert explicit_disable_args.games_enable is False

    explicit_enable_args = parser.parse_args(["--games-enable"])
    assert explicit_enable_args.games_enable is True


def test_dashboard_parser_supports_file_transfer_auto_accept_flag_and_env_default() -> None:
    parser = _build_parser(env_file_transfer_auto_accept="1")

    env_default_args = parser.parse_args([])
    assert env_default_args.file_transfer_auto_accept is True

    explicit_disable_args = parser.parse_args(["--no-file-transfer-auto-accept"])
    assert explicit_disable_args.file_transfer_auto_accept is False

    explicit_enable_args = parser.parse_args(["--file-transfer-auto-accept"])
    assert explicit_enable_args.file_transfer_auto_accept is True


def test_file_transfer_enable_requires_traffic_disclaimer() -> None:
    parser = argparse.ArgumentParser()
    args = argparse.Namespace(
        file_transfer_enable=True,
        file_transfer_max_bytes=64 * 1024,
        accept_file_transfer_traffic_disclaimer=False,
    )

    with pytest.raises(SystemExit) as exc:
        _validate_sideband_traffic_startup_args(args, parser=parser)

    assert exc.value.code == 2


def test_file_transfer_enable_accepts_traffic_disclaimer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = argparse.ArgumentParser()
    args = argparse.Namespace(
        file_transfer_enable=True,
        file_transfer_max_bytes=64 * 1024,
        accept_file_transfer_traffic_disclaimer=True,
    )

    _validate_sideband_traffic_startup_args(args, parser=parser)

    out = capsys.readouterr().out
    assert "file transfer enabled" in out
    assert "File transfer size cap" in out
    assert "BBS" not in out


def _add_mesh_connection_args(
    parser: argparse.ArgumentParser,
    *,
    default_mesh_port: str,
) -> None:
    parser.add_argument("--mesh-port", default=default_mesh_port)
