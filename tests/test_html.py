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
    assert "Meshyface" in html
    assert "Rev: v0.1.0 (abc123)" in html
    assert "History: on (7d retention, 5000 rows max)" in html
    assert "const refreshMs = 3000;" in html
    assert "setInterval(pollOnce, refreshMs);" in html


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
    assert 'id="self-radio-profile"' in html
    assert 'id="self-radio-menu"' in html
    assert 'id="self-radio-copy-id-btn"' in html


def test_render_html_includes_files_view_structure_tokens():
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
    assert 'data-view="files"' in html
    assert 'id="files-destination-input"' in html
    assert 'id="files-use-selected-btn"' in html
    assert 'id="files-send-channel-select"' in html
    assert 'id="files-input"' in html
    assert 'id="files-send-btn"' in html
    assert 'id="files-send-status"' in html
    assert 'id="files-console-log"' in html
    assert 'id="files-console-copy-btn"' in html
    assert 'id="files-console-clear-btn"' in html
    assert 'id="files-transfer-table"' in html


def test_render_html_includes_console_text_size_control():
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
    assert 'id="live-console"' in html
    assert 'id="console-terminal-screen"' in html
    assert 'id="console-command-input"' in html
    assert 'id="console-timestamps"' in html
    assert 'id="console-filter-input"' in html
    assert 'placeholder="Filter console text (e.g. ack -C2)..."' in html
    assert 'id="console-font-size-select"' in html


def test_render_html_includes_public_zork_handoff_toggle():
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
    assert 'id="bots-game-public-start-enabled"' in html


def test_render_html_includes_channel_control_center_structure():
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
    assert 'id="channels-fetch-settings-btn"' in html
    assert 'id="channels-apply-status"' in html
    assert 'id="settings-channels-table"' in html
    assert 'id="settings-channels-experimental-toggle"' in html
    assert 'id="channels-overview"' in html
    assert "Observed" in html
    assert "Channel Activity" in html
    assert "Advanced" in html


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
    assert 'id="favorite-menu-toggle-btn"' in html
    assert 'id="favorite-menu"' in html
    assert 'id="favorite-menu-saved-list"' in html
    assert 'id="favorites-list"' in html
    assert 'id="saved-node-details"' in html
