import os
import time

from meshdash import html_assets


def test_asset_template_cache_reloads_when_file_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(html_assets, "_ASSETS_DIR", tmp_path)
    html_assets.clear_asset_template_cache()

    template = tmp_path / "sample.tmpl"
    template.write_text("alpha", encoding="utf-8")
    assert html_assets.render_asset_template("sample.tmpl") == "alpha"

    template.write_text("beta", encoding="utf-8")
    now_ns = time.time_ns() + 1_000_000
    os.utime(template, ns=(now_ns, now_ns))

    assert html_assets.render_asset_template("sample.tmpl") == "beta"
