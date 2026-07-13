from types import SimpleNamespace

from meshdash.dashboard_runtime_context import build_dashboard_runtime_context
from meshdash.dashboard_runtime_loaders import DashboardRuntimeLoaders
from meshdash.file_transfer_protocol import (
    FILE_TRANSFER_PORTNUM,
    build_file_transfer_ack_frame,
    encode_file_transfer_frame,
    parse_file_transfer_frame_text,
)
from meshdash.revision import RevisionInfo
from meshdash.services_file_transfer_inbound import (
    InboundFileTransferService,
    build_inbound_file_transfer_service,
)
from meshdash.state_node_contracts import CollectedNodes
from meshdash.state_service import build_dashboard_state_typed
from meshdash.tracker_snapshot_contracts import empty_tracker_snapshot


def _make_iface(*, local_num: int = 0x12345678, sender_num: int = 0x01020304):
    return SimpleNamespace(
        nodesByNum={
            local_num: {"user": {"id": f"!{local_num:08x}"}},
            sender_num: {"user": {"id": f"!{sender_num:08x}"}},
        }
    )


def _packet(
    text: str,
    *,
    to_num: int = 0x12345678,
    channel: int = 2,
    packet_id: int | None = None,
) -> dict[str, object]:
    frame = parse_file_transfer_frame_text(text)
    assert frame is not None
    packet: dict[str, object] = {
        "from": 0x01020304,
        "to": to_num,
        "channel": channel,
        "decoded": {
            "payload": encode_file_transfer_frame(frame),
            "portnum": FILE_TRANSFER_PORTNUM,
        },
    }
    if packet_id is not None:
        packet["id"] = packet_id
    return packet


def _service(
    sent_messages: list[dict[str, object]],
    **kwargs: object,
) -> InboundFileTransferService:
    return build_inbound_file_transfer_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **values: sent_messages.append(dict(values)) or {"ok": True},
        **kwargs,
    )


def test_file_transfer_protocol_parses_meta_and_builds_compact_ack() -> None:
    parsed = parse_file_transfer_frame_text(
        "MF_FILE_V2|M|abcd1234|hello%20mesh.txt|320|2|raw|320"
    )

    assert parsed == {
        "kind": "meta",
        "transfer_id": "abcd1234",
        "file_name": "hello mesh.txt",
        "file_size": 320,
        "total_chunks": 2,
        "codec": "raw",
        "original_file_size": 320,
    }
    assert (
        build_file_transfer_ack_frame(
            transfer_id="abcd1234",
            total_chunks=2,
            received_indexes={0, 1},
        )
        == "MF_FILE_V2|A|abcd1234|2|2|AA=="
    )


def test_file_transfer_protocol_final_ack_stays_compact_for_large_transfers() -> None:
    frame = build_file_transfer_ack_frame(
        transfer_id="abcd1234",
        total_chunks=1024,
        received_indexes=range(1024),
    )

    assert frame == "MF_FILE_V2|A|abcd1234|1024|1024|AA=="
    assert len(frame.encode("utf-8")) < 200


def test_file_transfer_protocol_rejects_unsafe_metadata_and_chunks() -> None:
    assert (
        parse_file_transfer_frame_text(
            "MF_FILE_V2|M|abcd1234|sample.bin|1025|7|raw|1025",
            max_file_bytes=1024,
        )
        is None
    )
    assert (
        parse_file_transfer_frame_text(
            "MF_FILE_V2|M|abcd1234|sample.bin|128|999999|raw|128"
        )
        is None
    )
    assert (
        parse_file_transfer_frame_text(
            "MF_FILE_V2|C|abcd1234|0|" + ("AQ" * 65)
        )
        is None
    )


def test_receiver_does_not_accept_metadata_without_a_script_action() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages)
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320")

    service.on_receive(packet, _make_iface())

    assert sent_messages == []
    assert service.get_runtime()["active_sessions"] == 0


def test_script_accept_action_sends_initial_ack_for_direct_metadata() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages, now_monotonic_fn=lambda: 10.0)

    result = service.accept_offer(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320"),
        _make_iface(),
    )

    assert result == {
        "ok": True,
        "accepted": True,
        "sender_id": "!01020304",
        "transfer_id": "abcd1234",
        "channel_index": 2,
    }
    assert sent_messages == [
        {
            "text": "MF_FILE_V2|A|abcd1234|0|2|AA==",
            "destination": "!01020304",
            "channel_index": 2,
        }
    ]


def test_script_boundary_hex_payload_is_restored_before_validation() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages)
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    decoded = packet["decoded"]
    assert isinstance(decoded, dict)
    payload = decoded["payload"]
    assert isinstance(payload, bytes)
    decoded["payload"] = payload.hex()

    result = service.accept_offer(packet)

    assert result["accepted"] is True
    assert len(sent_messages) == 1


def test_script_accept_uses_numeric_headers_and_rejects_broadcast() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages, meta_peer_cooldown_seconds=0)
    direct = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    direct["fromId"] = "!99999999"

    direct_result = service.accept_offer(direct, _make_iface())
    broadcast_result = service.accept_offer(
        _packet(
            "MF_FILE_V2|M|abcd5678|sample.bin|64|1|raw|64",
            to_num=0xFFFFFFFF,
        ),
        _make_iface(),
    )

    assert direct_result["sender_id"] == "!01020304"
    assert sent_messages[0]["destination"] == "!01020304"
    assert broadcast_result == {
        "ok": False,
        "error": "File offer is not addressed to this node",
    }


def test_script_accept_rejects_non_metadata_and_oversized_offers() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages, max_file_bytes=1024)

    chunk_result = service.accept_offer(
        _packet("MF_FILE_V2|C|abcd1234|0|AQID")
    )
    oversized = _packet("MF_FILE_V2|M|abcd1234|sample.bin|1025|7|raw|1025")
    oversized_result = service.accept_offer(oversized)

    assert chunk_result["ok"] is False
    assert oversized_result["ok"] is False
    assert sent_messages == []


def test_script_accept_rate_limits_unique_metadata_admission() -> None:
    sent_messages: list[dict[str, object]] = []
    monotonic = [10.0]
    service = _service(
        sent_messages,
        now_monotonic_fn=lambda: monotonic[0],
        meta_peer_cooldown_seconds=2,
        meta_global_cooldown_seconds=0.25,
    )

    first = service.accept_offer(
        _packet("MF_FILE_V2|M|abcd1234|first.bin|64|1|raw|64", packet_id=1)
    )
    second = service.accept_offer(
        _packet("MF_FILE_V2|M|abcd5678|second.bin|64|1|raw|64", packet_id=2)
    )
    monotonic[0] = 13.0
    third = service.accept_offer(
        _packet("MF_FILE_V2|M|abcd9012|third.bin|64|1|raw|64", packet_id=3)
    )

    assert first["accepted"] is True
    assert second == {"ok": True, "accepted": False, "rate_limited": True}
    assert third["accepted"] is True
    assert service.get_runtime()["active_sessions"] == 2


def test_script_accept_suppresses_exact_offer_replays() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages)
    packet = _packet(
        "MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64",
        packet_id=41,
    )

    assert service.accept_offer(packet)["accepted"] is True
    assert service.accept_offer(dict(packet)) == {
        "ok": True,
        "accepted": False,
        "duplicate": True,
    }
    assert len(sent_messages) == 1


def test_close_rejects_actions_and_clears_sessions() -> None:
    sent_messages: list[dict[str, object]] = []
    service = _service(sent_messages)
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    service.accept_offer(packet)

    service.close()
    result = service.accept_offer(packet)

    assert result == {"ok": False, "error": "Inbound file receiver is closed"}
    assert service.get_runtime()["ok"] is False
    assert service.get_runtime()["available"] is False
    assert service.get_runtime()["active_sessions"] == 0


def test_accepted_session_tracks_chunk_progress_and_completion() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = _service(
        sent_messages,
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
    )
    service.accept_offer(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320", packet_id=1)
    )
    now["value"] = 10.1
    service.on_receive(_packet("MF_FILE_V2|C|abcd1234|0|AQID", packet_id=2))
    now["value"] = 10.2
    service.on_receive(_packet("MF_FILE_V2|C|abcd1234|1|BAUG", packet_id=3))

    assert [row["text"] for row in sent_messages] == [
        "MF_FILE_V2|A|abcd1234|0|2|AA==",
        "MF_FILE_V2|A|abcd1234|1|2|AQ==",
        "MF_FILE_V2|A|abcd1234|2|2|AA==",
    ]
    runtime = service.get_runtime()
    session = runtime["sessions"][0]
    assert session["source"] == "script_accept"
    assert session["received_indexes"] == [0, 1]
    assert session["percent"] == 100.0
    assert session["complete"] is True


def test_accepted_sessions_bind_chunks_to_the_offer_channel() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = _service(
        sent_messages,
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
    )
    service.accept_offer(
        _packet(
            "MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64",
            channel=2,
            packet_id=1,
        )
    )
    now["value"] = 10.1
    service.on_receive(
        _packet("MF_FILE_V2|C|abcd1234|0|AQID", channel=3, packet_id=2)
    )
    now["value"] = 10.2
    service.on_receive(
        _packet("MF_FILE_V2|C|abcd1234|0|AQID", channel=2, packet_id=3)
    )

    assert [row["channel_index"] for row in sent_messages] == [2, 2]
    assert service.get_runtime()["sessions"][0]["received_chunks"] == 1


def test_inbound_receiver_enforces_exact_session_limit() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = _service(
        sent_messages,
        now_monotonic_fn=lambda: now["value"],
        max_sessions=2,
        meta_peer_cooldown_seconds=0,
        meta_global_cooldown_seconds=0,
    )

    for index, transfer_id in enumerate(("abcd0001", "abcd0002", "abcd0003")):
        now["value"] = 10.0 + index
        service.accept_offer(
            _packet(
                f"MF_FILE_V2|M|{transfer_id}|sample.bin|64|1|raw|64",
                packet_id=index + 1,
            )
        )

    runtime = service.get_runtime()
    assert runtime["active_sessions"] == 2
    assert {row["transfer_id"] for row in runtime["sessions"]} == {
        "abcd0002",
        "abcd0003",
    }


def test_dashboard_state_exposes_file_transfer_runtime_summary() -> None:
    class _TrackerWithFileTransferRuntime:
        def snapshot(self, by_id: dict[str, dict[str, object]]) -> object:
            return empty_tracker_snapshot()

        def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
            return {}

        def load_node_capabilities(self) -> dict[str, dict[str, object]]:
            return {}

        def get_file_transfer_runtime(self) -> dict[str, object]:
            return {
                "ok": True,
                "available": True,
                "active_sessions": 1,
                "sessions": [{"transfer_id": "abcd1234"}],
            }

    payload = build_dashboard_state_typed(
        iface=object(),
        tracker=_TrackerWithFileTransferRuntime(),
        target="test",
        started_at=1_800_000_000,
        storage_probe_path=None,
        revision_info=RevisionInfo(
            version="0.0.0",
            commit="test",
            label="test",
            title="test",
        ),
        collect_nodes_fn=lambda iface: CollectedNodes(
            rows=[],
            full=[],
            by_id={},
            with_position_count=0,
        ),
        collect_local_state_safe_fn=lambda iface, *, collect_local_state_fn: ({}, None),
        get_radio_connection_status_fn=lambda iface: None,
    )

    assert payload.summary["file_transfer"]["available"] is True
    assert payload.summary["file_transfer"]["active_sessions"] == 1


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"


class _Tracker:
    def __init__(self, packet_limit: int, history_store: object) -> None:
        self.packet_limit = packet_limit
        self.history_store = history_store

    def on_receive(self, *_args: object, **_kwargs: object) -> None:
        return None


def test_runtime_wires_receiver_without_implicitly_accepting_offers(tmp_path) -> None:
    subscriptions: list[tuple[object, str]] = []
    sent_messages: list[dict[str, object]] = []
    iface = _make_iface()
    args = SimpleNamespace(
        history_db=str(tmp_path / "history.sqlite3"),
        no_history=True,
        seed_from_node_db=False,
        history_max_rows=1000,
        history_retention_days=7,
        history_event_max_rows=1000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=25,
        show_secrets=False,
        debug_mode=False,
        node_history_hours=72,
        node_history_max_points=1440,
        refresh_ms=3000,
        reset_ticker_scale_on_restart=False,
        http_host="127.0.0.1",
        http_port=0,
        games_enable=False,
        plugins_enable=False,
        file_transfer_enable=True,
        file_transfer_max_bytes=1024,
    )

    def _loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
        def _state() -> dict[str, object]:
            return {}

        return DashboardRuntimeLoaders(
            state_fn=_state,
            node_history_fn=lambda *_args, **_kwargs: {},
            summary_metrics_fn=lambda *_args, **_kwargs: {},
            send_chat_fn=lambda **values: sent_messages.append(dict(values))
            or {"ok": True},
        )

    context = build_dashboard_runtime_context(
        args,
        mesh_target_label_fn=lambda _args: "/dev/ttyUSB0 (serial)",
        open_mesh_interface_fn=lambda _args: iface,
        history_store_cls=lambda **_kwargs: object(),
        dashboard_tracker_cls=_Tracker,
        subscribe_fn=lambda callback, topic: subscriptions.append((callback, topic)),
        seed_tracker_fn=lambda _tracker, _iface: None,
        revision_info_fn=_RevisionInfo,
        send_chat_message_fn=lambda **_kwargs: {},
        send_reaction_packet_fn=lambda **_kwargs: None,
        get_local_node_id_fn=lambda _iface: "!12345678",
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
        utc_now_fn=lambda: "2026-06-07T00:00:00Z",
        build_state_fn=lambda **_kwargs: {},
        build_state_snapshot_loader_fn=lambda *_args, **_kwargs: lambda: {},
        build_node_history_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    callbacks = [
        callback
        for callback, topic in subscriptions
        if topic == "meshtastic.receive"
        and getattr(getattr(callback, "__self__", None), "__class__", None).__name__
        == "InboundFileTransferService"
    ]
    assert len(callbacks) == 1
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320")
    callbacks[0](packet, iface)
    assert sent_messages == []

    receiver = context.tracker._file_transfer_inbound_service
    assert receiver.accept_offer(packet, iface)["accepted"] is True
    assert len(sent_messages) == 1
