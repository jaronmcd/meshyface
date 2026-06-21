from meshdash.api_metrics import (
    DashboardApiMetrics,
    build_prometheus_metrics_text,
    derive_live_packet_count,
    derive_node_count,
    derive_radio_link_up,
    estimate_packet_rate_per_second,
)


def test_estimate_packet_rate_uses_recent_packet_timestamps() -> None:
    payload = {
        "traffic": {
            "recent_packets": [
                {"rx_time_unix": 100},
                {"time_unix": "105"},
                {"packet_rx_time_unix": 110},
                {"rx_time": "1970-01-01T00:01:55Z"},
                {"bad": "ignored"},
            ]
        }
    }

    assert estimate_packet_rate_per_second(payload) == 0.2
    assert estimate_packet_rate_per_second({"traffic": {"recent_packets": [{"rx_time_unix": 1}]}}) == 0.0
    assert estimate_packet_rate_per_second({"traffic": {"recent_packets": "not-list"}}) == 0.0


def test_derive_counts_and_radio_link_states() -> None:
    assert derive_node_count({"summary": {"node_count": "7"}}) == 7
    assert derive_node_count({"summary": {"node_count": "-2"}}) == 0
    assert derive_live_packet_count({"summary": {"live_packet_count": 12.5}}) == 12
    assert derive_live_packet_count({"summary": {"live_packet_count": "-1"}}) == 0

    assert derive_radio_link_up({"tracker_error": "radio link lost: serial down"}) == 0
    assert derive_radio_link_up({"summary": {}}) == -1
    assert derive_radio_link_up({"summary": {"radio_connection": {"state": "connected"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_connection": {"status": "offline"}}}) == 0
    assert derive_radio_link_up({"summary": {"radio_connection": {"is_connected": "yes"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_connection": {"connected": "false"}}}) == 0
    assert derive_radio_link_up({"summary": {"radio_connection": {"wifi": {"is_connected": "true"}}}}) == 1
    assert derive_radio_link_up(
        {"summary": {"radio_connection": {"wifi": {"connected": "false"}, "serial": {"is_connected": "no"}}}}
    ) == 0
    assert derive_radio_link_up({"summary": {"radio_connection": {"wifi": {"connected": "maybe"}}}}) == -1
    assert derive_radio_link_up({"summary": {"radio_link": {"connected": True}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_link": {"is_connected": "yes"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_link": {"state": "connected"}}}) == 1
    assert derive_radio_link_up({"summary": {"radio_link": {"state": "connecting"}}}) == 0
    assert derive_radio_link_up({"summary": {"radio_link": {"status": "offline"}}}) == 0
    assert derive_radio_link_up({"summary": {"radio_link": {"state": "maybe"}}}) == -1
    assert derive_radio_link_up(
        {
            "summary": {
                "radio_link": {"connected": False},
                "radio_connection": {"state": "connected"},
            }
        }
    ) == 0


def test_build_prometheus_metrics_text_renders_state_and_counter_values() -> None:
    text = build_prometheus_metrics_text(
        state_payload={
            "summary": {
                "node_count": 3,
                "live_packet_count": 9,
                "radio_link": {"connected": True},
                "radio_connection": {"state": "up"},
            },
            "traffic": {
                "recent_packets": [
                    {"rx_time_unix": 10},
                    {"rx_time_unix": 20},
                ]
            },
        },
        counters={
            "state_poll_requests_total": "4",
            "state_poll_errors_total": "1",
            "write_auth_denied_total": "2",
            "private_mode_blocks_total": "3",
        },
    )

    assert "meshdash_packet_rate_per_second 0.100000" in text
    assert "meshdash_live_packet_count 9" in text
    assert "meshdash_node_count 3" in text
    assert "meshdash_state_poll_requests_total 4" in text
    assert "meshdash_state_poll_errors_total 1" in text
    assert "meshdash_write_auth_denied_total 2" in text
    assert "meshdash_private_mode_blocks_total 3" in text
    assert "meshdash_radio_link_up 1" in text


def test_dashboard_api_metrics_records_and_snapshots_counters() -> None:
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
