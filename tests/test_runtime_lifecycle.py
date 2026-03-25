from meshdash.runtime_lifecycle import (
    close_runtime_resources,
    emit_startup_status,
    serve_until_stopped,
)
from meshdash.revision import RevisionInfo


def test_emit_startup_status_public_bind_history_enabled():
    lines = []

    emit_startup_status(
        http_host="0.0.0.0",
        bound_host="0.0.0.0",
        bound_port=8877,
        show_secrets=False,
        revision_info=RevisionInfo(version="0.1.0", commit="abc123", label="L", title="T"),
        history_enabled=True,
        history_db_path="/tmp/history.sqlite3",
        history_retention_days=7,
        history_max_rows=5000,
        history_event_retention_days=30,
        history_event_max_rows=200000,
        history_rollup_retention_days=365,
        guess_lan_ipv4_fn=lambda: "192.168.1.241",
        out_fn=lines.append,
    )

    assert "Dashboard server running." in lines
    assert "Bound to: 0.0.0.0:8877" in lines
    assert "Open from this computer: http://127.0.0.1:8877" in lines
    assert "Open from Wi-Fi devices: http://192.168.1.241:8877" in lines
    assert "Secrets are redacted. Use --show-secrets to display full values." in lines
    assert "Revision: v0.1.0 (abc123)" in lines
    assert any("History DB: /tmp/history.sqlite3" in line for line in lines)
    assert "Press Ctrl+C to stop." in lines


def test_emit_startup_status_bound_host_history_disabled_no_redaction_line():
    lines = []

    emit_startup_status(
        http_host="127.0.0.1",
        bound_host="127.0.0.1",
        bound_port=8877,
        show_secrets=True,
        revision_info=RevisionInfo(version="0.1.0", commit="abc123", label="L", title="T"),
        history_enabled=False,
        history_db_path="/tmp/history.sqlite3",
        history_retention_days=7,
        history_max_rows=5000,
        history_event_retention_days=30,
        history_event_max_rows=200000,
        history_rollup_retention_days=365,
        guess_lan_ipv4_fn=lambda: "192.168.1.241",
        out_fn=lines.append,
    )

    assert "Open: http://127.0.0.1:8877" in lines
    assert "History DB: disabled" in lines
    assert all("Secrets are redacted" not in line for line in lines)
    assert all("Open from Wi-Fi devices:" not in line for line in lines)


def test_emit_startup_status_public_bind_without_lan_ip_uses_placeholder():
    lines = []

    emit_startup_status(
        http_host="0.0.0.0",
        bound_host="0.0.0.0",
        bound_port=8877,
        show_secrets=True,
        revision_info=RevisionInfo(version="0.1.0", commit="abc123", label="L", title="T"),
        history_enabled=False,
        history_db_path="/tmp/history.sqlite3",
        history_retention_days=7,
        history_max_rows=5000,
        history_event_retention_days=30,
        history_event_max_rows=200000,
        history_rollup_retention_days=365,
        guess_lan_ipv4_fn=lambda: None,
        out_fn=lines.append,
    )

    assert "Open from this computer: http://127.0.0.1:8877" in lines
    assert "Open from Wi-Fi devices: http://<this-computer-ip>:8877" in lines


def test_serve_until_stopped_handles_keyboard_interrupt():
    lines = []

    class _Server:
        def serve_forever(self, poll_interval=0.5):
            raise KeyboardInterrupt()

    serve_until_stopped(_Server(), poll_interval=0.5, out_fn=lines.append)
    assert lines == ["Stopping dashboard..."]


def test_close_runtime_resources_closes_server_iface_and_optional_history():
    class _Server:
        def __init__(self):
            self.closed = False

        def server_close(self):
            self.closed = True

    class _Iface:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class _History:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    server = _Server()
    iface = _Iface()
    history = _History()
    close_runtime_resources(server=server, iface=iface, history_store=history)

    assert server.closed is True
    assert iface.closed is True
    assert history.closed is True
