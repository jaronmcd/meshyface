import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js
from meshdash.html_template import render_html


def _dashboard_js() -> str:
    return build_dashboard_js(
        refresh_ms=3000,
        node_history_hours=24,
        node_history_max_points=1000,
    )


def _dashboard_html() -> str:
    return render_html(
        refresh_ms=3000,
        packet_limit=200,
        show_secrets=False,
        history_enabled=True,
        history_max_rows=200,
        history_retention_days=7,
        node_history_hours=24,
        node_history_max_points=1000,
        revision_label="test",
        revision_title="test",
    )


def test_dashboard_has_noninteractive_promoted_node_context_bridge() -> None:
    html = _dashboard_html()

    assert 'id="chat-node-context-bridge"' in html
    assert 'aria-hidden="true" hidden' in html
    assert 'class="chat-node-context-bridge-glow"' in html
    assert 'class="chat-node-context-bridge-offscreen-boundary"' in html
    assert 'class="chat-node-context-bridge-edge chat-node-context-bridge-edge-top"' in html
    assert 'class="chat-node-context-bridge-edge chat-node-context-bridge-edge-target"' in html
    assert 'chat-node-context-bridge-anchor' not in html


def test_promoted_node_bridge_tracks_roster_scroll_without_extra_identity_pill() -> None:
    js = _dashboard_js()

    assert 'id="chat-node-details-promoted-identity"' not in js
    assert "function syncChatNodeContextBridge() {" in js
    assert 'targetList.addEventListener("scroll", () => {' in js
    assert "scheduleChatNodeContextBridgeSync();" in js


def test_clicking_selected_roster_node_collapses_its_details() -> None:
    js = _dashboard_js()

    assert "const collapseSelectedNodeDetails = !!(" in js
    assert "selectedBeforeClick === nodeId" in js
    assert "setChatNodeDetailsDrawerExpanded(false, {" in js
    assert "!collapseSelectedNodeDetails" in js


def test_promoted_bridge_anchors_to_selected_row_without_scrolling() -> None:
    js = _dashboard_js()

    assert "let anchorTopViewportY;" in js
    assert "let anchorBottomViewportY;" in js
    assert "rowRect.top + 1" in js
    assert "rowRect.bottom - 1" in js
    assert "anchorBottomViewportY = anchorTopViewportY;" in js
    assert "anchorTopViewportY = anchorBottomViewportY;" in js
    assert 'const offscreenBoundary = position === "visible"' in js
    assert "listRect.left - workspaceRect.left" in js
    assert "listRect.right - workspaceRect.left" in js
    assert "anchorTopY.toFixed(1)" in js
    assert "anchorBottomY.toFixed(1)" in js
    assert "const targetEdge =" in js
    assert "hostRect.left - workspaceRect.left" in js
    assert "hostRect.top - workspaceRect.top" in js
    assert "hostRect.bottom - workspaceRect.top" in js
    assert "window.getComputedStyle(promotedHost).borderTopLeftRadius" in js
    assert "const targetRadius = Math.max(0, Math.min(" in js
    assert "const targetCurveX = targetX + targetRadius;" in js
    assert "const targetTopInner = targetTop + targetRadius;" in js
    assert "const targetBottomInner = targetBottom - targetRadius;" in js
    assert " Q " in js
    assert 'bridge.querySelector(".chat-node-context-bridge-edge-target")' in js
    assert 'target.setAttribute("d", targetEdge)' in js
    assert 'row.classList.remove("chat-node-context-bridge-source")' in js
    assert 'geometry.row.classList.add("chat-node-context-bridge-source")' in js
    assert 'rowStyle.getPropertyValue("--node-profile-theme-base").trim()' in js
    assert 'rowStyle.getPropertyValue("--chat-member-node-bg").trim()' not in js
    assert 'CSS.supports("color", profileBridgeColor)' in js
    assert 'bridge.style.setProperty("--chat-node-context-bridge-fill-color", bridgeColor)' in js
    assert 'geometry.row.style.setProperty("--chat-node-context-bridge-fill-color", bridgeColor)' in js
    assert "chat-node-context-bridge-anchor" not in js
    assert "((rowRect.left + rowRect.right) / 2) - workspaceRect.left" in js
    assert "centerChatNodeNavigatorRow" not in js
    assert "scheduleChatNodeNavigatorRowCenter" not in js
    assert 'typeof isChatNodeDetailsPromotedActive === "function"' in js
    assert "&& isChatNodeDetailsPromotedActive()" in js


def test_promoted_node_context_bridge_is_lightweight_and_click_through() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-node-context-bridge {" in css
    assert "pointer-events: none;" in css
    assert "filter: blur(12px);" in css
    assert "var(--chat-node-context-bridge-fill-color, var(--ui-accent)) 5.5%" in css
    assert "stroke: color-mix(in srgb, var(--ui-accent) 42%, transparent);" in css
    assert ".chat-node-context-bridge-offscreen-boundary" in css
    assert ".chat-member-item.chat-node-context-bridge-source" in css
    assert "inset 0 0 0 999px" in css
    assert ".chat-node-context-bridge-anchor" not in css
    assert ".chat-node-details-promoted-identity" not in css
