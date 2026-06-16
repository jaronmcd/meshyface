import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_readme_drops_unpkg_and_carto_runtime_language() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "unpkg.com" not in readme
    assert "cartocdn" not in readme.lower()
    assert "CARTO" not in readme
    assert "Leaflet CDN" not in readme


def test_public_docs_do_not_expose_local_benchmark_target() -> None:
    roots = [
        Path("README.md"),
        Path("docs"),
        Path("PUBLICATION_CHECKLIST.md"),
        Path("THIRD_PARTY_NOTICES.md"),
        Path("THIRD_PARTY_PYTHON_DEPENDENCIES.md"),
        Path("benchmarks/gui_responsiveness"),
        Path("third_party/emoji_catalog_generation.md"),
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in {".md", ".json"}
            )
        else:
            files.append(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "192.168.1.87" not in text, path
        assert "change-me-please" not in text, path


def test_readme_history_retention_default_matches_cli() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "`--history-retention-days <days>`: default `30`" in readme


def test_third_party_notices_are_resolved_not_todo_language() -> None:
    notices = Path("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "Before public release" not in notices
    assert "confirm the applicable" not in notices
    assert "review them before public release" not in notices
    assert "Colossal Cave" not in notices
    assert "previously reviewed" not in notices
    assert "was removed" not in notices
    assert "unpkg.com" not in notices
    assert "cartocdn" not in notices.lower()
    assert "https://operations.osmfoundation.org/policies/tiles/" in notices
    assert "Meshyface does not proxy OSM tiles" in notices


def test_built_dashboard_js_uses_exact_osm_tile_url_and_attribution() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in js
    assert "{s}.tile.openstreetmap.org" not in js
    assert "OpenStreetMap</a> contributors" in js


def test_built_dashboard_js_exposes_offline_atlas_attribution_toggle() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    assert "Offline atlas:" in js
    assert "GeoNames" in js
    assert "setMapOfflineAtlasAttributionVisible(" in js


def test_shared_meshyface_psk_is_bundled_without_hotspot_default_password() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )
    hotspot_script = Path("scripts/deploy_hotspot.sh").read_text(encoding="utf-8")
    legacy_psk = "base64:" + "u2yfVqp2J8P+Uer6z9OnNGwORpCCSNF4GKbzYgya9jM="
    legacy_hotspot_default = "meshyface" + "203"
    assert legacy_psk in js
    assert legacy_hotspot_default not in hotspot_script
    assert "change-me-please" not in hotspot_script
