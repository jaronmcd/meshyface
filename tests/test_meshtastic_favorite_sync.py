import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.html_js import build_dashboard_js


def test_dashboard_js_includes_meshtastic_favorite_sync_state() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'const meshtasticFavoritePinnedSyncStorageKey = "meshDashboardMeshtasticFavoritePinnedSyncIdsV1";' in js
    assert "const meshtasticFavoriteSyncedPinnedNodeIds = new Set();" in js
    assert "function loadMeshtasticFavoritePinnedSyncIds()" in js
    assert "function persistMeshtasticFavoritePinnedSyncIds()" in js
    assert "function syncPinnedNodesWithMeshtasticFavorites(state = latestState)" in js


def test_dashboard_js_boot_and_poll_wire_meshtastic_favorite_sync() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert 'runBootStep("loadMeshtasticFavoritePinnedSyncIds", () => loadMeshtasticFavoritePinnedSyncIds());' in js
    assert "syncPinnedNodesWithMeshtasticFavorites(state);" in js
