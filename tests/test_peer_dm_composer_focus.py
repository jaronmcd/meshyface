from collections.abc import Callable


def test_peer_dm_thread_preserves_composer_between_poll_renders(
    dashboard_js_factory: Callable[..., str],
) -> None:
    js = dashboard_js_factory()

    assert "const nextThreadHtml = `<section" in js
    assert "const threadMarkupChanged = host.__meshPeerDmThreadHtml !== nextThreadHtml;" in js
    assert "host.__meshPeerDmThreadHtml = nextThreadHtml;" in js
    assert 'value="${escAttr(draft)}"' not in js
    assert "const inputHasFocus = document.activeElement === input;" in js
    assert "if (threadMarkupChanged || (!inputHasFocus && input.value !== draft)) {" in js
    assert 'if (input instanceof HTMLInputElement && input.dataset.bound !== "1") {' in js
    assert 'if (sendBtn instanceof HTMLButtonElement && sendBtn.dataset.bound !== "1") {' in js
    assert 'if (ev.key !== "Enter" || ev.shiftKey) return;' in js
    assert "void submitMessage();" in js
    assert "if (bodyEl instanceof HTMLElement && threadMarkupChanged) {" in js
