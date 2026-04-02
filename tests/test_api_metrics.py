from meshdash.api_metrics import (
    DashboardApiMetrics,
    _coerce_optional_bool,
    build_prometheus_metrics_text,
    derive_live_packet_count,
    derive_node_count,
    derive_radio_link_up,
    estimate_packet_rate_per_second,
)


def test_estimate_packet_rate_returns_zero_when_recent_packets_missing():
    assert estimate_packet_rate_per_second(None) == 0.0
    assert estimate_packet_rate_per_second({"traffic": {"recent_packets": "not-a-list"}}) == 0.0
    assert estimate_packet_rate_per_second({"traffic": {"recent_packets": [{"rx_time_unix": 123}]}}) == 0.0


def test_estimate_packet_rate_handles_zero_span_and_time_text_fallbacks():
    zero_span = {
        "traffic": {
            "recent_packets": [
                {"rx_time_unix": 100},
                {"time_unix": 100},
                {"packet_rx_time_unix": "100"},
            ]
        }
    }
    assert estimate_packet_rate_per_second(zero_span) == 3.0

    text_time_payload = {
        "traffic": {
            "recent_packets": [
                {"rx_time": "2024-01-01 00:00:00Z"},
                {"captured_at": "2024-01-01 00:00:10Z"},
                {"time": "invalid"},
            ]
        }
    }
    assert estimate_packet_rate_per_second(text_time_payload) == 0.1


def test_derive_counts_clamp_and_default_missing_summary_values():
    assert derive_node_count({"summary": {"node_count": 7}}) == 7
    assert derive_live_packet_count({"summary": {"live_packet_count": "11"}}) == 11
    assert derive_node_count({"summary": {"node_count": -9}}) == 0
    assert derive_live_packet_count({"summary": {"live_packet_count": -4}}) == 0
    assert derive_node_count({"summary": object()}) == 0
    assert derive_live_packet_count("not-a-mapping") == 0


def test_coerce_optional_bool_supports_common_truthy_and_falsy_values():
    assert _coerce_optional_bool(True) is True
    assert _coerce_optional_bool(False) is False
    assert _coerce_optional_bool(None) is None
    assert _coerce_optional_bool("YES") is True
    assert _coerce_optional_bool("online") is True
    assert _coerce_optional_bool("off") is False
    assert _coerce_optional_bool("disconnected") is False
    assert _coerce_optional_bool("maybe") is None


def test_derive_radio_link_up_covers_error_state_hints_and_direct_flags():
    assert derive_radio_link_up({"tracker_error": "Radio link lost during poll"}) == 0
    assert derive_radio_link_up({"summary": {}}) == -1
    assert derive_radio_link_up({"summary": {"radio_connection": {"state": "CONNECTED"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_connection": {"status": "down"}}}) == 0
    assert derive_radio_link_up({"summary": {"radio_connection": {"is_connected": "yes"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_connection": {"connected": "false"}}}) == 0


def test_derive_radio_link_up_covers_nested_transport_signals():
    up = {"summary": {"radio_connection": {"wifi": {"connected": "true"}}}}
    assert derive_radio_link_up(up) == 1

    down = {
        "summary": {
            "radio_connection": {
                "wifi": {"connected": "false"},
                "ethernet": {"is_connected": "0"},
            }
        }
    }
    assert derive_radio_link_up(down) == 0

    unknown = {"summary": {"radio_connection": {"wifi": {"connected": "??"}}}}
    assert derive_radio_link_up(unknown) == -1


def test_build_prometheus_metrics_text_formats_expected_metrics_and_counters():
    state_payload = {
        "summary": {
            "node_count": 4,
            "live_packet_count": 12,
            "radio_connection": {"state": "connected"},
        },
        "traffic": {
            "recent_packets": [
                {"rx_time_unix": 200},
                {"time_unix": 205},
            ]
        },
    }
    counters = {
        "state_poll_requests_total": "9",
        "state_poll_errors_total": 2,
        "write_auth_denied_total": -6,
        "private_mode_blocks_total": "3",
    }

    text = build_prometheus_metrics_text(state_payload=state_payload, counters=counters)

    assert "meshdash_packet_rate_per_second 0.200000" in text
    assert "meshdash_live_packet_count 12" in text
    assert "meshdash_node_count 4" in text
    assert "meshdash_state_poll_requests_total 9" in text
    assert "meshdash_state_poll_errors_total 2" in text
    assert "meshdash_write_auth_denied_total 0" in text
    assert "meshdash_private_mode_blocks_total 3" in text
    assert "meshdash_radio_link_up 1" in text
    assert text.endswith("\n")


def test_dashboard_api_metrics_snapshot_tracks_all_counters():
    metrics = DashboardApiMetrics()
    metrics.record_state_poll_request()
    metrics.record_state_poll_request()
    metrics.record_state_poll_error()
    metrics.record_write_auth_denied()
    metrics.record_private_mode_block()

    assert metrics.snapshot() == {
        "state_poll_requests_total": 2,
        "state_poll_errors_total": 1,
        "write_auth_denied_total": 1,
        "private_mode_blocks_total": 1,
    }
