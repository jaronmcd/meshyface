from types import SimpleNamespace

import pytest

import mesh_dashboard
from meshdash.dashboard_runner_impl import (
    _build_offline_runtime_context,
    run_dashboard_runtime,
)


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "commit": self.commit,
            "label": self.label,
            "title": self.title,
        }


def _dashboard_args(tmp_path):
    return SimpleNamespace(
        mesh_port="/dev/mesh_py_missing_radio",
        mesh_host=None,
        mesh_tcp_port=4403,
        http_host="127.0.0.1",
        http_port=0,
        refresh_ms=3000,
        packet_limit=25,
        show_secrets=False,
        debug_mode=False,
        private_mode=False,
        api_token=None,
        history_db=str(tmp_path / "history.sqlite3"),
        history_max_rows=1000,
        history_retention_days=7,
        history_event_max_rows=1000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        no_history=True,
        seed_from_node_db=False,
        node_history_hours=72,
        node_history_max_points=1440,
        theme_presets=None,
        theme_preset="custom",
        theme_settings_file=str(tmp_path / "theme.json"),
        file_transfer_enable=False,
        file_transfer_max_bytes=65536,
        zork_enable=False,
    )


def test_run_dashboard_degrades_when_radio_stack_is_unavailable(monkeypatch, tmp_path) -> None:
    args = _dashboard_args(tmp_path)
    captured: dict[str, object] = {}

    def _capture_runtime(call_args, **kwargs):
        captured["args"] = call_args
        captured.update(kwargs)

    monkeypatch.setattr(mesh_dashboard, "meshtastic", None)
    monkeypatch.setattr(mesh_dashboard, "pub", None)
    monkeypatch.setattr(mesh_dashboard, "_run_dashboard_runtime_helper", _capture_runtime)

    mesh_dashboard.run_dashboard(args)

    assert captured["args"] is args
    captured["subscribe_fn"](object(), "meshtastic.receive")
    with pytest.raises(RuntimeError, match="meshtastic Python package is required"):
        captured["open_mesh_interface_fn"](args)


def test_runtime_serves_offline_page_before_first_radio_open(tmp_path) -> None:
    args = _dashboard_args(tmp_path)
    events: list[str] = []

    class _OneShotServer:
        def __init__(self, address, handler_cls) -> None:
            del handler_cls
            events.append("server_init")
            self.server_address = (address[0], 18080)

        def serve_forever(self, poll_interval: float = 0.5) -> None:
            del poll_interval
            events.append("serve")

        def shutdown(self) -> None:
            events.append("shutdown")

        def server_close(self) -> None:
            events.append("server_close")

    def _open_mesh_interface(_args):
        events.append("open")
        raise RuntimeError("radio absent")

    run_dashboard_runtime(
        args,
        mesh_target_label_fn=lambda _args: "/dev/mesh_py_missing_radio (serial)",
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=lambda **_kwargs: object(),
        dashboard_tracker_cls=lambda **_kwargs: object(),
        subscribe_fn=lambda _callback, _topic: None,
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        build_state_fn=lambda **_kwargs: {},
        build_node_history_loader_fn=lambda _store, **_kwargs: lambda *_args: {},
        build_online_activity_loader_fn=lambda _store, **_kwargs: lambda *_args: {},
        build_summary_metrics_loader_fn=lambda _store, **_kwargs: lambda *_args: {},
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "local",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-04-23T00:00:00Z",
        render_html_fn=lambda **_kwargs: "<html></html>",
        make_http_handler_fn=lambda *_args, **_kwargs: object,
        guess_lan_ipv4_fn=lambda: None,
        default_chat_max_bytes=200,
        threading_http_server_cls=_OneShotServer,
    )

    assert "serve" in events
    assert "open" not in events[: events.index("serve") + 1]


def test_offline_runtime_keeps_standalone_zork_disabled_by_default(tmp_path) -> None:
    args = _dashboard_args(tmp_path)
    context = _build_offline_runtime_context(
        args,
        startup_error=RuntimeError("radio absent"),
        connecting=True,
        mesh_target_label_fn=lambda _args: "/dev/mesh_py_missing_radio (serial)",
        revision_info_fn=_RevisionInfo,
        utc_now_fn=lambda: "2026-04-23T00:00:00Z",
    )

    play_fn = getattr(context.state_fn, "play_standalone_zork_fn", None)
    assert play_fn is None


def test_offline_runtime_enables_standalone_zork_when_requested(tmp_path) -> None:
    args = _dashboard_args(tmp_path)
    args.zork_enable = True
    context = _build_offline_runtime_context(
        args,
        startup_error=RuntimeError("radio absent"),
        connecting=True,
        mesh_target_label_fn=lambda _args: "/dev/mesh_py_missing_radio (serial)",
        revision_info_fn=_RevisionInfo,
        utc_now_fn=lambda: "2026-04-23T00:00:00Z",
    )

    play_fn = getattr(context.state_fn, "play_standalone_zork_fn", None)
    assert callable(play_fn)

    start = play_fn(text="zork", session_id="offline-zork")  # type: ignore[misc]
    assert start["ok"] is True
    assert start["active_session"] is True
    assert start["session_id"] == "offline-zork"

    follow_up = play_fn(text="look", session_id="offline-zork")  # type: ignore[misc]
    assert follow_up["ok"] is True
    assert follow_up["active_session"] is True
