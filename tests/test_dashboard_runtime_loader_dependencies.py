from meshdash.dashboard_runtime_loader_contracts import DashboardRuntimeLoaderDependencies
from meshdash.dashboard_runtime_loader_dependencies import (
    build_dashboard_runtime_loader_dependencies_from_legacy_args,
)
from meshdash.revision import RevisionInfo


def test_build_dashboard_runtime_loader_dependencies_from_legacy_args_maps_fields():
    revision = RevisionInfo(version="0.1.0", commit="abc", label="L", title="T")
    sentinel = {
        "iface": object(),
        "tracker": object(),
        "send_lock": object(),
        "started_at": 123.0,
        "target": "mesh-target",
        "show_secrets": False,
        "history_db_path": "/tmp/db.sqlite3",
        "history_store": object(),
        "default_node_history_hours": 72,
        "default_node_history_points": 1440,
        "send_chat_message_fn": object(),
        "send_reaction_packet_fn": object(),
        "get_local_node_id_fn": object(),
        "default_chat_max_bytes": 220,
        "normalize_single_emoji_fn": object(),
        "to_int_fn": object(),
        "utc_now_fn": object(),
        "build_state_fn": object(),
        "build_state_snapshot_loader_fn": object(),
        "build_node_history_loader_fn": object(),
        "build_online_activity_loader_fn": object(),
        "build_summary_metrics_loader_fn": object(),
        "build_send_chat_loader_fn": object(),
    }

    deps = build_dashboard_runtime_loader_dependencies_from_legacy_args(
        **sentinel,
        revision_info=revision,
    )

    assert isinstance(deps, DashboardRuntimeLoaderDependencies)
    assert deps.revision_info is revision
    for key, value in sentinel.items():
        assert getattr(deps, key) is value
