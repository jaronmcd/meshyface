import argparse

import pytest

from mesh_dashboard import _warn_if_cli_api_token
from meshdash.cli_args_http import add_http_runtime_args


def _build_http_parser(default_api_token: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    add_http_runtime_args(
        parser,
        default_http_host="127.0.0.1",
        default_http_port=8877,
        default_refresh_ms=3000,
        default_packet_limit=250,
        default_api_token=default_api_token,
    )
    return parser


def test_api_token_env_default_does_not_mark_cli_source() -> None:
    parser = _build_http_parser(default_api_token="env-token")

    args = parser.parse_args([])

    assert args.api_token == "env-token"
    assert args.api_token_supplied_via_cli is False


def test_api_token_cli_flag_marks_cli_source_and_overrides_env() -> None:
    parser = _build_http_parser(default_api_token="env-token")

    args = parser.parse_args(["--api-token", "cli-token"])

    assert args.api_token == "cli-token"
    assert args.api_token_supplied_via_cli is True


def test_api_token_help_prefers_environment_variable() -> None:
    parser = _build_http_parser()

    help_text = parser.format_help()

    assert "Prefer MESH_DASH_API_TOKEN" in help_text
    assert "process listings" in help_text


def test_warn_if_cli_api_token_prints_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(
        api_token="secret-token",
        api_token_supplied_via_cli=True,
    )

    _warn_if_cli_api_token(args)

    out = capsys.readouterr().out
    assert "--api-token exposes the token" in out
    assert "MESH_DASH_API_TOKEN" in out


def test_warn_if_cli_api_token_stays_quiet_for_env_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = argparse.Namespace(
        api_token="secret-token",
        api_token_supplied_via_cli=False,
    )

    _warn_if_cli_api_token(args)

    assert capsys.readouterr().out == ""
