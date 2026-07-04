from pathlib import Path


def test_chat_node_telemetry_tools_include_store_forward_history() -> None:
    src = Path(
        "meshdash/assets/dashboard.js.chat.state.messaging.peers.tmpl"
    ).read_text(encoding="utf-8")

    assert 'id: "store_forward_history"' in src
    assert 'label: "S&F History"' in src
    assert 'command: "request-store-forward-history"' in src
    assert "history_window_minutes: 240" in src
