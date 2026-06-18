import json
from types import SimpleNamespace

import pytest


def test_channel_settings_helpers_cover_edge_coercions() -> None:
    from meshdash.api_input_channels import (
        _clean_settings,
        _coerce_bool,
        _coerce_int,
        parse_channel_settings_request,
    )

    assert _coerce_bool(object()) is True
    assert _coerce_int(True) == 1
    assert _coerce_int(float("nan")) is None
    assert _coerce_int(2.75) == 2
    assert _coerce_int("   ") is None
    assert _coerce_int(object()) is None
    assert _clean_settings({1: "ignored", "module_settings": ["ignored"]}) == {}

    request = parse_channel_settings_request(
        json.dumps({"downlink_enabled": "", "include_all": "unexpected"}).encode("utf-8")
    )
    assert request.include_all is True
    assert request.settings == {"downlink_enabled": False}


def test_radio_settings_helpers_cover_edge_cleaning_paths() -> None:
    from meshdash.api_input_radio import (
        _clean_actions,
        _clean_fixed_position,
        _clean_owner,
        _clean_section_map,
        _clean_time_sync,
        _clean_update_object,
        _clean_update_value,
        _coerce_bool,
        parse_radio_settings_request,
    )

    assert _coerce_bool(False) is False
    assert _coerce_bool("unexpected") is True
    assert _clean_update_value([1, object()]) is None
    assert _clean_update_value(object()) is None
    assert _clean_update_value(
        {1: "ignored", "nested": {"keep": 1, "drop": [object()], "keep_none": None}, "none": None}
    ) == {"nested": {"keep": 1, "keep_none": None}, "none": None}
    assert _clean_update_object({1: "ignored", "dropped": object(), "cleared": None}, field_name="x") == {
        "cleared": None
    }
    assert _clean_section_map({1: {"ignored": True}, "bad": [], "ok": {"x": 1}}, field_name="local") == {
        "ok": {"x": 1}
    }
    assert _clean_actions({1: True, "set_time": "maybe"}) == {"set_time": True}
    assert _clean_owner(
        {1: "ignored", "short_name": None, "long_name": None, "is_licensed": object()}
    ) == {"short_name": None, "long_name": None, "is_licensed": True}
    assert _clean_fixed_position({1: 44, "latitude": object(), "lat": None}) == {"lat": None}
    assert _clean_time_sync({1: "ignored", "enabled": False, "server": object(), "timezone": None}) == {
        "enabled": False,
        "timezone": None,
    }

    request = parse_radio_settings_request(
        json.dumps(
            {
                "reset_nodedb": "yes",
                "reset_dashboard_db": "on",
                "set_time": "off",
                "regenerate_node_id": "true",
                "set_fixed_position": 1,
                "clear_fixed_position": 0,
            }
        ).encode("utf-8")
    )
    assert request.actions == {
        "reset_nodedb": True,
        "reset_dashboard_db": True,
        "set_time": False,
        "regenerate_node_id": True,
        "set_fixed_position": True,
        "clear_fixed_position": False,
    }


def test_api_metrics_helpers_handle_non_mapping_and_degenerate_packets() -> None:
    from meshdash.api_metrics import (
        _coerce_optional_bool,
        _packet_timestamp_unix,
        _state_summary,
        _state_traffic,
        estimate_packet_rate_per_second,
    )

    assert _state_summary([]) == {}
    assert _state_traffic([]) == {}
    assert _packet_timestamp_unix([]) is None
    assert _packet_timestamp_unix({"rx_time": "2024-01-01 00:00:00Z"}) == 1704067200
    assert estimate_packet_rate_per_second(
        {"traffic": {"recent_packets": [{"rx_time_unix": 5}, {"time_unix": 5}]}}
    ) == 2.0
    assert _coerce_optional_bool(True) is True
    assert _coerce_optional_bool("maybe") is None


def test_state_payload_coercion_identity_error_and_passthrough_paths() -> None:
    from meshdash.state_payload_contracts import (
        DashboardStatePayload,
        StateTrafficPayload,
        coerce_dashboard_state_payload,
        coerce_state_traffic_payload,
        normalize_state_payload_for_api,
    )

    traffic = StateTrafficPayload(edges=[], port_counts=[], recent_packets=[], recent_chat=[])
    assert coerce_state_traffic_payload(traffic) is traffic
    with pytest.raises(TypeError):
        coerce_state_traffic_payload(object())

    dashboard = DashboardStatePayload(
        generated_at="now",
        summary={},
        summary_error=None,
        my_info=None,
        my_info_error=None,
        metadata=None,
        metadata_error=None,
        local_state={},
        local_state_error=None,
        nodes_error=None,
        tracker_error=None,
        tracker_saved_counts_error=None,
        tracker_capabilities_error=None,
        nodes=[],
        history_caps={},
        nodes_full=[],
        traffic=traffic,
    )
    assert coerce_dashboard_state_payload(dashboard) is dashboard
    with pytest.raises(TypeError):
        coerce_dashboard_state_payload(object())
    assert normalize_state_payload_for_api(dashboard) == dashboard.as_dict()
    assert normalize_state_payload_for_api({"summary": {}, "traffic": {}})["local_node_id"] == "local"
    assert normalize_state_payload_for_api("unchanged") == "unchanged"


def test_theme_normalizers_cover_short_hex_fallbacks_and_luminance_branch() -> None:
    from meshdash.theme import (
        _channel_luminance,
        normalize_theme_base_color,
        normalize_theme_color_depth,
    )

    assert normalize_theme_base_color("#abc") == "#aabbcc"
    assert normalize_theme_color_depth(object(), fallback=17) == 17
    assert _channel_luminance(0) == 0.0


def test_theme_presets_cover_invalid_tokens_and_path_read(tmp_path) -> None:
    from meshdash.theme_presets import _normalize_theme_tokens, default_theme_presets, load_theme_presets

    assert _normalize_theme_tokens({"--present": "x"}, required_keys={"--missing"}) is None

    defaults = default_theme_presets()
    custom_light = {**defaults["default"]["light"], "--theme-base-color": "#101010"}
    custom_dark = {**defaults["default"]["dark"], "--theme-base-color": "#202020"}
    path = tmp_path / "themes.json"
    path.write_text(json.dumps({"file": {"light": custom_light, "dark": custom_dark}}), encoding="utf-8")

    loaded = load_theme_presets(str(path))
    assert loaded["file"]["light"]["--theme-base-color"] == "#101010"
    assert loaded["file"]["dark"]["--theme-base-color"] == "#202020"


def test_node_identity_helpers_cover_local_fallbacks() -> None:
    from meshdash.nodes_identity import get_local_node_id, get_local_node_num, get_node_id_from_num

    assert get_node_id_from_num(object(), None, broadcast_num=None) is None

    iface = SimpleNamespace(myInfo=None, localNode=SimpleNamespace(nodeNum=123), nodesByNum={})
    assert get_local_node_num(iface) == 123

    calls: list[object] = []

    def flaky_to_int(value: object) -> int | None:
        calls.append(value)
        return 123 if len(calls) == 1 else None

    assert get_local_node_id(
        SimpleNamespace(myInfo={"num": 123}, nodesByNum={}),
        broadcast_num=None,
        to_jsonable_fn=lambda value: value,
        to_int_fn=flaky_to_int,
    ) == "!0000007b"


def test_bot_registry_deduplicates_normalized_app_names(monkeypatch) -> None:
    import meshdash.bot_apps.registry as registry
    from meshdash.bot_commands import BotCommandSpec

    class App:
        def __init__(self, name: str) -> None:
            self.SPEC = BotCommandSpec(name=name, usage=name, description=name)

    first = App("!Dup")
    second = App("dup")
    unnamed = App("")
    external = App("DUP")

    monkeypatch.setattr(registry, "build_internal_bot_apps", lambda: [first, second, unnamed])
    monkeypatch.setattr(registry, "load_external_bot_apps", lambda *, env=None: [external])

    assert registry.build_builtin_bot_apps(env={}) == [first]


def test_tracker_helpers_cover_nan_hex_neighbor_and_storage_paths() -> None:
    from meshdash.tracker_edges import _to_metric_value
    from meshdash.tracker_ingest import _normalize_packet_node_id
    from meshdash.tracker_observation import apply_tracker_observation
    from meshdash.tracker_runtime_chat import record_tracker_local_chat
    from meshdash.tracker_storage import apply_tracker_storage_updates

    assert _to_metric_value(float("nan")) is None
    assert _normalize_packet_node_id("ABCDEF12") == "!abcdef12"
    assert _normalize_packet_node_id("not-a-node") == "not-a-node"

    calls: list[tuple[object, object]] = []

    def record_direct_edge_observation_fn(**kwargs):
        calls.append((kwargs["from_id"], kwargs["to_id"]))
        return (str(kwargs["from_id"]), str(kwargs["to_id"]))

    keys = apply_tracker_observation(
        parsed={
            "decoded": {},
            "from_id": "a",
            "to_id": "b",
            "rx_time": 1,
            "hops": 1,
            "portnum": "TEXT_MESSAGE_APP",
            "neighbor_info_edges": [object(), {"from_id": "n", "to_id": "m", "rx_time": 2, "rx_snr": 3}],
        },
        include_live_count=True,
        session_edges={},
        historical_edges={},
        port_counts={},
        apply_routing_delivery_update_fn=lambda *args, **kwargs: None,
        extract_update_fn=lambda decoded: None,
        set_delivery_state_fn=lambda *args, **kwargs: None,
        record_direct_edge_observation_fn=record_direct_edge_observation_fn,
    )
    assert keys == (("a", "b"), ("n", "m"))
    assert calls == [("a", "b"), ("n", "m")]

    assert record_tracker_local_chat(
        text="hi",
        from_id="a",
        to_id="b",
        channel_index=0,
        message_id=None,
        reply_id=None,
        emoji=None,
        emoji_codepoint=None,
        is_reaction=False,
        ack_requested=False,
        retry_of=None,
        bot_command=None,
        recent_chat=[],
        history_store=None,
        build_tracker_local_entry_fn=lambda **kwargs: None,
        append_local_chat_entry_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("not called")),
        build_local_chat_entry_fn=lambda **kwargs: {},
        utc_now_fn=lambda: "now",
        now_unix_fn=lambda: 1.0,
        to_int_fn=lambda value: None,
        emoji_from_codepoint_fn=lambda value: None,
    ) is False

    class Store:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []
            self.packets: list[dict[str, object]] = []
            self.chats: list[dict[str, object]] = []

        def save_connection_event(self, **kwargs) -> None:
            self.events.append(kwargs)

        def save_packet(self, packet: dict[str, object]) -> None:
            self.packets.append(packet)

        def save_chat(self, chat: dict[str, object]) -> None:
            self.chats.append(chat)

    store = Store()
    recent_packets: list[dict[str, object]] = []
    recent_chat: list[dict[str, object]] = []
    packet = {"id": 1}
    chat = {"from": "a", "text": "hello"}
    apply_tracker_storage_updates(
        recent_packets=recent_packets,
        recent_chat=recent_chat,
        history_store=store,
        include_live_count=True,
        direct_keys=(("a", "b"),),
        rx_time=10,
        portnum=123,
        hops=2,
        packet_entry=packet,
        chat_entry=chat,
    )
    assert recent_packets == [packet]
    assert recent_chat == [chat]
    assert store.events == [
        {"from_id": "a", "to_id": "b", "rx_time": 10, "portnum": "123", "hops": 2}
    ]
    assert store.packets == [packet]
    assert store.chats == [chat]


def test_small_utility_paths_cover_policy_and_asset_cache() -> None:
    import meshdash.html_assets as html_assets
    from meshdash.history_store_policy import build_history_store_policy

    policy = build_history_store_policy(
        max_rows=0,
        retention_days=-1,
        event_max_rows=1,
        event_retention_days=-2,
        rollup_retention_days=3,
    )
    assert policy.max_rows == 100
    assert policy.event_max_rows == 1000
    assert policy.retention_seconds == 0
    assert policy.event_retention_seconds == 0
    assert policy.rollup_retention_seconds == 259200

    html_assets._ASSET_TEMPLATE_CACHE["example"] = (1, "cached")
    html_assets.clear_asset_template_cache()
    assert html_assets._ASSET_TEMPLATE_CACHE == {}
