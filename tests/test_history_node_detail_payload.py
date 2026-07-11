import json

from meshdash.history_node_analytics import (
    _build_packet_series_payload,
    _collect_packet_history,
    _collect_packet_timestamps,
    _extract_packet_time_unix,
    _normalize_node_id as _normalize_history_node_id,
    _packet_channel_text,
    _packet_hops,
    _packet_text_preview,
    build_node_history_payload,
)
from meshdash.history_node_names import (
    _extract_time_unix,
    _extract_user_candidates,
    _normalize_node_id,
    _preferred_display_name,
    build_name_change_chat_entries,
    build_name_history_points,
)


def _row(created: object, summary: dict[str, object] | object, packet: dict[str, object] | object) -> tuple[object, str, str]:
    return (
        created,
        json.dumps(summary) if isinstance(summary, dict) else str(summary),
        json.dumps(packet) if isinstance(packet, dict) else str(packet),
    )


def test_name_history_extracts_candidates_sorts_changes_and_filters_other_nodes() -> None:
    rows = [
        _row(
            1_700_000_130,
            {"from": "ffffffff", "rx_time_unix": 1_700_000_130},
            {"decoded": {"user": {"shortName": "Other", "longName": "Wrong"}}},
        ),
        _row(
            1_700_000_100,
            {"from": "01020304", "rx_time_unix": 1_700_000_100, "portnum": "NODEINFO_APP"},
            {"user": {"shortName": "Mesh", "longName": "Mesh Node"}},
        ),
        _row(
            1_700_000_120,
            {"from": "01020304", "rx_time_unix": 1_700_000_120},
            {"decoded": {"nodeInfo": {"id": "!01020304", "short_name": "MN\x00"}}},
        ),
        _row(
            1_700_000_110,
            {"from_id": "!01020304", "rx_time_unix": 1_700_000_110},
            {"decoded": {"payload": {"user": {"id": "01020304", "shortName": "Mesh", "longName": "Mesh Node"}}}},
        ),
        _row(
            1_700_000_140,
            {"from": "01020304", "rx_time_unix": 1_700_000_140},
            {"decoded": {"admin": {"user": {"node_id": "99999999", "shortName": "Skip"}}}},
        ),
        _row(1_700_000_150, "not json", "not json"),
    ]

    history = build_name_history_points(node_id="01020304", packet_rows=rows)

    assert [(point["time_unix"], point["short_name"], point["long_name"]) for point in history] == [
        (1_700_000_100, "Mesh", "Mesh Node"),
        (1_700_000_120, "MN", "Mesh Node"),
    ]
    assert history[0]["node_id"] == "!01020304"
    assert history[0]["source_portnum"] == "NODEINFO_APP"
    assert history[1]["source_portnum"] is None
    assert build_name_history_points(node_id="", packet_rows=rows) == []


def test_name_change_chat_entries_emit_status_rows_after_first_seen_name() -> None:
    entries = build_name_change_chat_entries(
        recent_packets=[
            object(),  # type: ignore[list-item]
            {"summary": {}, "packet": {"decoded": {"user": {"shortName": "No sender"}}}},
            {
                "summary": {
                    "from": "!01020304",
                    "rx_time_unix": 1_700_000_100,
                    "portnum": "",
                    "channel": -1,
                },
                "packet": {"channel": "3", "decoded": {"nodeinfo": {"shortName": "Mesh", "longName": "Mesh Node"}}},
            },
            {
                "summary": {"from": "!01020304", "rx_time_unix": 1_700_000_110, "channel": 1},
                "packet": {"decoded": {"payload": {"user": {"node_id": "01020304", "long_name": "Mesh Relay"}}}},
            },
            {
                "summary": {"from": "!01020304", "rx_time_unix": 1_700_000_120},
                "packet": {"decoded": {"user": {"shortName": "Mesh", "longName": "Mesh Relay"}}},
            },
        ]
    )

    assert len(entries) == 1
    assert entries[0]["kind"] == "status"
    assert entries[0]["status_event"] == "name_change"
    assert entries[0]["status_subject"] == "!01020304"
    assert entries[0]["status_old_name"] == "Mesh Node"
    assert entries[0]["status_new_name"] == "Mesh Relay"
    assert entries[0]["portnum"] == "NODEINFO_APP"
    assert entries[0]["channel"] == 1
    assert entries[0]["text"] == "Mesh Node changed their name to Mesh Relay"


def test_name_change_chat_entries_use_local_receipt_before_radio_time() -> None:
    entries = build_name_change_chat_entries(
        recent_packets=[
            {
                "summary": {
                    "from": "!01020304",
                    "captured_at": "2023-11-14 22:15:00Z",
                    "rx_time_unix": 1_700_000_200,
                },
                "packet": {"decoded": {"user": {"longName": "Old Name"}}},
            },
            {
                "summary": {
                    "from": "!01020304",
                    "captured_at": "2023-11-14 22:15:10Z",
                    "rx_time_unix": 1_700_000_000,
                },
                "packet": {"decoded": {"user": {"longName": "New Name"}}},
            },
        ]
    )

    assert len(entries) == 1
    assert entries[0]["text"] == "Old Name changed their name to New Name"
    assert entries[0]["captured_at"] == "2023-11-14 22:15:10Z"
    assert entries[0]["rx_time"] == "2023-11-14 22:15:10Z"


def test_name_private_helpers_cover_normalization_and_time_parsing() -> None:
    assert _normalize_node_id("0xffffffff") == "^all"
    assert _normalize_node_id("01020304") == "!01020304"
    assert _normalize_node_id(" !ABCDEF12 ") == "!abcdef12"
    assert _normalize_node_id("not-hex") == "not-hex"
    assert _preferred_display_name(short_name=" short ", long_name="", fallback="fallback") == "short"
    assert _preferred_display_name(short_name="", long_name="\x00 long ", fallback="fallback") == "long"
    assert _preferred_display_name(short_name="", long_name="", fallback="\x00 fallback ") == "fallback"

    packet = {"user": {"shortName": "Packet"}}
    decoded = {
        "user": {"shortName": "Decoded"},
        "payload": {"user": {"shortName": "Nested"}, "longName": "Payload"},
        "admin": "bad",
    }
    assert [candidate.get("shortName") for candidate in _extract_user_candidates(packet, decoded)] == [
        "Packet",
        "Decoded",
        "Nested",
        None,
    ]
    assert _extract_time_unix(0, "bad", 1_700_000_000, now_unix=1_700_000_100) == 1_700_000_000
    assert _extract_time_unix(1_800_000_000, now_unix=1_700_000_100) is None


def test_packet_history_summarizes_direction_peer_metadata_and_text() -> None:
    long_text = "x" * 220
    rows = [
        _row(
            1_700_000_100,
            {
                "from": "01020304",
                "to": "05060708",
                "rx_time_unix": 1_700_000_100,
                "portnum": "TEXT_MESSAGE_APP",
                "packet_id": "12",
                "hops": "2",
                "rx_snr": "4.25",
                "rx_rssi": "-80",
                "channel": "Primary",
                "decoded_text": long_text,
            },
            {"decoded": {"text": "ignored"}},
        ),
        _row(
            1_700_000_110,
            {"to": "!01020304", "rxTime": 1_700_000_110, "is_reaction": True, "emoji": ":thumbs_up:"},
            {
                "fromId": "!05060708",
                "decoded": {"portnum": "REACTION_APP", "channelIndex": 2},
                "hopStart": 7,
                "hopLimit": 4,
                "rxSnr": 3.5,
                "rxRssi": -91,
                "id": 99,
            },
        ),
        _row(
            1_700_000_120,
            {},
            {
                "from_id": "!09090909",
                "to_id": "^all",
                "rx_time_unix": 1_700_000_120,
                "portnum": "NODEINFO_APP",
                "rx_snr": "1",
                "rx_rssi": "-100",
                "decoded": {"channel": "LongFast"},
            },
        ),
        _row(0, {"from": "01020304"}, {}),
        _row(1_700_000_130, [], []),
    ]

    entries, total = _collect_packet_history(node_id="01020304", packet_rows=rows, max_rows=2)

    assert total == 4
    assert len(entries) == 2
    assert entries[0]["direction"] == "sent"
    assert entries[0]["peer_id"] == "05060708"
    assert entries[0]["hops"] == 2
    assert entries[0]["packet_id"] == 12
    assert entries[0]["rx_snr"] == 4.25
    assert entries[0]["rx_rssi"] == -80.0
    assert entries[0]["channel"] == "Primary"
    assert str(entries[0]["text"]).endswith("...")
    assert len(str(entries[0]["text"])) == 180
    assert entries[1]["direction"] == "recv"
    assert entries[1]["peer_id"] == "!05060708"
    assert entries[1]["portnum"] == "REACTION_APP"
    assert entries[1]["channel"] == "Ch 2"
    assert entries[1]["hops"] == 3
    assert entries[1]["packet_id"] == 99
    assert entries[1]["text"] == "reaction :thumbs_up:"


def test_packet_helpers_cover_channels_hops_text_and_timestamps() -> None:
    assert _normalize_history_node_id("broadcast") == "^all"
    assert _normalize_history_node_id("ABCDEF12") == "!abcdef12"
    assert _normalize_history_node_id("custom") == "custom"
    assert _packet_hops({"hops": "-1", "hop_start": 5, "hop_limit": 3}, {}) == 2
    assert _packet_hops({}, {"hops": 0}) == 0
    assert _packet_hops({}, {"hopStart": 1, "hopLimit": 3}) is None
    assert _packet_hops({}, {}) is None
    assert _packet_channel_text({"channel": -1}, {"channel": "Secondary"}, {}) == "-1"
    assert _packet_channel_text({"channel": None}, {"channel": "Secondary"}, {}) == "Secondary"
    assert _packet_channel_text({}, {}, {"channel_index": 0}) == "Ch 0"
    assert _packet_channel_text({}, {}, {"channel": ""}) is None
    assert _packet_text_preview({}, {"text": " line\r\nnext "}) == "line\nnext"
    assert _packet_text_preview({"is_reaction": True}, {}) == "reaction"
    assert _packet_text_preview({}, {}) is None

    assert (
        _extract_packet_time_unix(
            1_700_000_010,
            {"rx_time_unix": 1_800_000_000},
            {"rxTime": 1_700_000_020},
            now_unix=1_700_000_100,
        )
        == 1_700_000_010
    )
    assert (
        _extract_packet_time_unix(
            None,
            {},
            {"decoded": {"rx_time_unix": 1_700_000_030}},
            now_unix=1_700_000_100,
        )
        == 1_700_000_030
    )
    assert _extract_packet_time_unix(None, [], [], now_unix=1_700_000_100) is None
    assert _collect_packet_timestamps(
        [
            _row(1_700_000_010, {}, {}),
            _row(1_700_000_010, {"rx_time_unix": 1_700_000_020}, {}),
            _row(0, {}, {}),
        ]
    ) == [1_700_000_010, 1_700_000_020]


def test_packet_series_payload_normalizes_rows_and_bucket_counts() -> None:
    class IterableRow:
        def __iter__(self):
            return iter((120, "nodeinfo", 2))

    series = _build_packet_series_payload(
        [
            (60, "chat", 2),
            [60, "unknown", "3"],
            IterableRow(),
            (120, "chat", -1),
            (0, "chat", 4),
            ("bad", "chat", 4),
            object(),
            (180,),
        ]
    )

    assert series["available"] is True
    assert series["series"]["all"] == [  # type: ignore[index]
        {"bucket_unix": 60, "packet_count": 5},
        {"bucket_unix": 120, "packet_count": 2},
    ]
    assert series["series"]["chat"] == [{"bucket_unix": 60, "packet_count": 2}]  # type: ignore[index]
    assert series["series"]["other"] == [{"bucket_unix": 60, "packet_count": 3}]  # type: ignore[index]
    assert series["series"]["nodeinfo"] == [{"bucket_unix": 120, "packet_count": 2}]  # type: ignore[index]
    assert _build_packet_series_payload([])["series"]["all"] == []  # type: ignore[index]


def test_build_node_history_payload_combines_metric_position_packet_and_name_data() -> None:
    packet_rows = [
        _row(
            1_700_000_100,
            {"from": "01020304", "to": "05060708", "rx_time_unix": 1_700_000_100, "decoded_text": "hello"},
            {"user": {"shortName": "Mesh", "longName": "Mesh Node"}},
        )
    ]
    metric_rows = [
        (
            1_700_000_060,
            2,
            7.5,
            2,
            3.0,
            4.5,
            -160,
            2,
            -90,
            -70,
            5,
            2,
            2,
            3,
            1_700_000_100,
        )
    ]
    position_rows = [(1_700_000_090, 30.0, -97.0, 100, 5)]
    packet_type_rows = [(1_700_000_060, "chat", 2), (1_700_000_060, "routing", 1)]

    payload = build_node_history_payload(
        node_id="01020304",
        window_hours=0,
        metric_rows=metric_rows,
        position_rows=position_rows,
        packet_rows=packet_rows,
        packet_type_rows=packet_type_rows,
    )

    assert payload["node_id"] == "01020304"
    assert payload["window_hours"] == 1
    assert payload["summary"]["total_packets"] == 2  # type: ignore[index]
    assert payload["summary"]["packet_history_count"] == 1  # type: ignore[index]
    assert payload["summary"]["packet_history_truncated"] is False  # type: ignore[index]
    assert payload["points"][0]["avg_snr"] == 3.75  # type: ignore[index]
    assert payload["positions"][0]["lat"] == 30.0  # type: ignore[index]
    assert payload["packet_timestamps"] == [1_700_000_100]
    assert payload["packet_history"][0]["direction"] == "sent"  # type: ignore[index]
    assert payload["name_history"][0]["long_name"] == "Mesh Node"  # type: ignore[index]
    assert payload["packet_series"]["series"]["all"] == [{"bucket_unix": 1_700_000_060, "packet_count": 3}]  # type: ignore[index]

    empty = build_node_history_payload(
        node_id="",
        window_hours=-1,
        metric_rows=[],
        position_rows=[],
        packet_rows=[],
        packet_type_rows=[],
    )
    assert empty["window_hours"] == 1
    assert empty["summary"] == {}
