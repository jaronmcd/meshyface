from meshdash.html import render_html


def test_render_html_includes_revision_and_runtime_values():
    html = render_html(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        revision_label="Rev: v0.1.0 (abc123)",
        revision_title="v0.1.0 / abc123",
    )
    assert "Meshtastic Dashboard" in html
    assert "Rev: v0.1.0 (abc123)" in html
    assert "History: on (7d retention, 5000 rows max)" in html
    assert "const refreshMs = 3000;" in html
    assert "setInterval(poll, refreshMs);" in html


def test_render_html_includes_chat_view_structure_tokens():
    html = render_html(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        revision_label="Rev: v0.1.0 (abc123)",
        revision_title="v0.1.0 / abc123",
    )
    assert 'data-view="chat"' in html
    assert 'id="chat-left-panel"' in html
    assert 'id="chat-feed"' in html
    assert 'id="chat-input"' in html
    assert 'id="chat-user-search-input"' in html


def test_render_html_includes_network_view_structure_tokens():
    html = render_html(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        revision_label="Rev: v0.1.0 (abc123)",
        revision_title="v0.1.0 / abc123",
    )
    assert 'data-view="network"' in html
    assert 'id="nodes-search-input"' in html
    assert 'id="nodes-table"' in html
    assert 'id="network-node-splitter"' in html
    assert 'id="network-node-history-host"' in html
    assert 'id="map"' in html


def test_render_html_includes_saved_view_structure_tokens():
    html = render_html(
        refresh_ms=3000,
        packet_limit=250,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=5000,
        history_retention_days=7,
        node_history_hours=72,
        node_history_max_points=1440,
        revision_label="Rev: v0.1.0 (abc123)",
        revision_title="v0.1.0 / abc123",
    )
    assert 'data-view="saved"' in html
    assert 'id="favorites-search-input"' in html
    assert 'id="favorites-clear-btn"' in html
    assert 'id="favorites-list"' in html
    assert 'id="saved-node-details"' in html
