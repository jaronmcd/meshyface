import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_css import build_dashboard_css
from meshdash.html_js import build_dashboard_js


def test_dashboard_js_marks_alert_messages_in_chat_feed() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const isAlertMessage = portnumKey === "ALERT_APP";' in js
    assert 'const alertClass = isAlertMessage ? " kind-alert" : "";' in js
    assert 'class="chat-feed-alert-pill" title="Alert packet">! Alert</span>' in js
    assert 'class="chat-monitor-alert-tag" title="Alert packet">[!]</span>' in js
    assert 'const alertClass = isAlertMessage ? " is-alert" : "";' in js
    assert 'class="peer-dm-popout-alert-chip" title="Alert packet">!</span>' in js


def test_dashboard_css_styles_alert_messages_in_chat_feed() -> None:
    css = build_dashboard_css(theme_css="")

    assert ".chat-feed-item.kind-alert {" in css
    assert ".chat-feed-alert-pill {" in css
    assert ".chat-feed.chat-feed-view-monitor .chat-monitor-alert-tag {" in css
    assert '[data-theme="dark"] .chat-feed-item.kind-alert {' in css
    assert '[data-theme="dark"] .chat-feed-alert-pill {' in css
    assert '[data-theme="dark"] .chat-feed.chat-feed-view-monitor .chat-monitor-alert-tag {' in css
    assert ".peer-dm-popout-msg.is-alert {" in css
    assert ".peer-dm-popout-alert-chip {" in css
    assert '[data-theme="dark"] .peer-dm-popout-msg.is-alert {' in css
    assert '[data-theme="dark"] .peer-dm-popout-alert-chip {' in css
