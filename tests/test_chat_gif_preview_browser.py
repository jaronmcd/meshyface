import base64
import shutil

import pytest

from meshdash.html_assets import render_asset_template
from meshdash.html_css import build_dashboard_css


pw_api = pytest.importorskip("playwright.sync_api")
GIF_BYTES = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@pytest.mark.gui_benchmark
@pytest.mark.parametrize("width", [320, 1280])
def test_chat_gif_links_load_fit_and_keep_link_on_failure(request, width):
    if not request.config.getoption("--run-gui-benchmark"):
        pytest.skip("pass --run-gui-benchmark for GIF browser checks")
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        pytest.skip("Chromium is required")
    helpers = render_asset_template("dashboard.js.chat.events.core.identity.text_utils.tmpl")
    css = build_dashboard_css(theme_css="")
    with pw_api.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.route("**/*", lambda route: route.fulfill(status=404, body="missing"))
            page.route("**/ok.GIF?*", lambda route: route.fulfill(content_type="image/gif", body=GIF_BYTES))
            page.route("**/api/chat/gif-preview?*", lambda route: route.fulfill(content_type="image/gif", body=GIF_BYTES))
            page.set_content(f"""<base href="https://dashboard.example/">
<style>{css}</style><div style="width: 100%; max-width: 180px">
<span id="chat" class="chat-feed-text chat-feed-text-inline"></span></div>
<script>{helpers}\nbindChatGifPreviews();</script>""")
            raw = (
                '<script>alert("unsafe")</script> 🌱\n'
                'See (https://images.example/ok.GIF?size=small&loop=1), '
                'https://tenor.com/iT6gMPRoaCs.gif and https://images.example/missing.gif. '
                'https://example.com/page?file=pretend.gif'
            )
            page.evaluate("raw => document.getElementById('chat').innerHTML = chatPlainTextToHtml(raw, true)", raw)
            images = page.locator(".chat-gif-preview")
            assert images.count() == 3
            page.wait_for_function("""() => [...document.querySelectorAll('.chat-gif-preview')]
                .every(img => img.complete && (img.naturalWidth > 0 || img.hidden))""")
            assert images.nth(0).evaluate("img => img.naturalWidth") == 1
            assert images.nth(1).evaluate("img => img.naturalWidth") == 1
            assert images.nth(2).is_hidden()
            link = page.locator('a[href="https://images.example/missing.gif"]')
            assert link.is_visible()
            assert link.inner_text() == "https://images.example/missing.gif"
            assert page.locator("#chat script").count() == 0
            assert page.locator("#chat .chat-inline-emoji").count() == 1
            assert page.locator("#chat br").count() == 1
            assert page.locator("#chat a").count() == 4
            for image in (images.nth(0), images.nth(1)):
                rect = image.bounding_box()
                assert rect["width"] <= 180
                assert rect["x"] + rect["width"] <= width
            assert page.evaluate("raw => chatPlainTextToHtml(raw, false).includes('<img')", raw) is False
            sources = page.evaluate("""() => [
                'javascript:alert(1)', 'data:image/gif;base64,AA',
                'https://user:secret@images.example/ok.gif', 'https://tenor.com/search/cats',
                'https://example.com/page?file=pretend.gif'
            ].map(chatGifPreviewSource)""")
            assert sources == [""] * 5
        finally:
            browser.close()
