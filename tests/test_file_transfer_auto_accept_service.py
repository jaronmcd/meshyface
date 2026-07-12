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
from meshdash.services_file_transfer_auto_accept import (
    build_file_transfer_auto_accept_service,
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


def _packet(text: str, *, to_num: int = 0x12345678, channel: int = 2) -> dict[str, object]:
    frame = parse_file_transfer_frame_text(text)
    assert frame is not None
    return {
        "from": 0x01020304,
        "to": to_num,
        "channel": channel,
        "decoded": {
            "payload": encode_file_transfer_frame(frame),
            "portnum": FILE_TRANSFER_PORTNUM,
        },
    }


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
    parsed = parse_file_transfer_frame_text(frame)
    assert parsed is not None
    assert parsed["received_count"] == 1024
    assert parsed["total_chunks"] == 1024


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
            "MF_FILE_V2|M|abcd1234|sample.bin|320|1|raw|320"
        )
        is None
    )
    assert (
        parse_file_transfer_frame_text(
            "MF_FILE_V2|C|abcd1234|0|" + ("AQ" * 65)
        )
        is None
    )


def test_file_transfer_ack_builder_rejects_oversized_work_before_iterating() -> None:
    class _MustNotIterate:
        def __iter__(self):
            raise AssertionError("received indexes must not be inspected")

    assert (
        build_file_transfer_ack_frame(
            transfer_id="abcd1234",
            total_chunks=999999999,
            received_indexes=_MustNotIterate(),
        )
        == ""
    )
    assert (
        build_file_transfer_ack_frame(
            transfer_id="abcd1234",
            total_chunks=1024,
            received_indexes={1023},
            max_frame_bytes=200,
        )
        == ""
    )


def test_auto_accept_sends_initial_ack_for_direct_meta() -> None:
    sent_messages: list[dict[str, object]] = []
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: 10.0,
    )

    service.on_receive(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320"),
        _make_iface(),
    )

    assert sent_messages == [
        {
            "text": "MF_FILE_V2|A|abcd1234|0|2|AA==",
            "destination": "!01020304",
            "channel_index": 2,
        }
    ]


def test_auto_accept_uses_numeric_header_identity_over_display_aliases() -> None:
    sent_messages: list[dict[str, object]] = []
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: 10.0,
    )
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320")
    packet["fromId"] = "!99999999"
    interface = _make_iface()
    interface.nodesByNum[0x01020304]["user"]["id"] = "!88888888"

    service.on_receive(packet, interface)

    assert sent_messages[0]["destination"] == "!01020304"


def test_auto_accept_rate_limits_unique_metadata_admission() -> None:
    sent_messages: list[dict[str, object]] = []
    monotonic = [10.0]
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: monotonic[0],
        meta_peer_cooldown_seconds=2,
        meta_global_cooldown_seconds=0.25,
    )

    service.on_receive(
        _packet("MF_FILE_V2|M|abcd1234|first.bin|64|1|raw|64"),
        _make_iface(),
    )
    service.on_receive(
        _packet("MF_FILE_V2|M|abcd5678|second.bin|64|1|raw|64"),
        _make_iface(),
    )

    assert len(sent_messages) == 1
    assert service.get_runtime()["active_sessions"] == 1
    monotonic[0] = 13.0
    service.on_receive(
        _packet("MF_FILE_V2|M|abcd9012|third.bin|64|1|raw|64"),
        _make_iface(),
    )
    assert len(sent_messages) == 2
    assert service.get_runtime()["active_sessions"] == 2


def test_auto_accept_ignores_metadata_over_configured_limit() -> None:
    sent_messages: list[dict[str, object]] = []
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        max_file_bytes=1024,
    )

    service.on_receive(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|1025|7|raw|1025"),
        _make_iface(),
    )

    assert sent_messages == []
    assert service.get_runtime()["active_sessions"] == 0


def test_auto_accept_close_disables_processing_and_clears_sessions() -> None:
    sent_messages: list[dict[str, object]] = []
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
    )
    packet = _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320")

    service.on_receive(packet, _make_iface())
    assert service.get_runtime()["active_sessions"] == 1
    service.close()
    service.on_receive(packet, _make_iface())

    assert service.get_runtime()["enabled"] is False
    assert service.get_runtime()["active_sessions"] == 0
    assert len(sent_messages) == 1


def test_auto_accept_acks_chunk_progress_and_final_completion() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
    )
    iface = _make_iface()

    service.on_receive(_packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320"), iface)
    now["value"] = 10.1
    service.on_receive(_packet("MF_FILE_V2|C|abcd1234|0|AQID"), iface)
    now["value"] = 10.2
    service.on_receive(_packet("MF_FILE_V2|C|abcd1234|1|BAUG"), iface)

    assert [row["text"] for row in sent_messages] == [
        "MF_FILE_V2|A|abcd1234|0|2|AA==",
        "MF_FILE_V2|A|abcd1234|1|2|AQ==",
        "MF_FILE_V2|A|abcd1234|2|2|AA==",
    ]
    runtime = service.get_runtime()
    assert runtime["active_sessions"] == 1
    assert runtime["sent_ack_count"] == 3
    assert runtime["sessions"] == [
        {
            "key": "!01020304|!12345678|abcd1234|2",
            "source": "backend_auto_accept",
            "authoritative": True,
            "sender_id": "!01020304",
            "receiver_id": "!12345678",
            "transfer_id": "abcd1234",
            "channel_index": 2,
            "file_name": "sample.bin",
            "file_size": 320,
            "original_file_size": 320,
            "codec": "raw",
            "total_chunks": 2,
            "received_chunks": 2,
            "missing_chunks": 0,
            "received_indexes": [0, 1],
            "percent": 100.0,
            "complete": True,
            "created_unix": runtime["sessions"][0]["created_unix"],
            "updated_unix": runtime["sessions"][0]["updated_unix"],
            "age_seconds": runtime["sessions"][0]["age_seconds"],
            "idle_seconds": runtime["sessions"][0]["idle_seconds"],
            "last_ack_age_seconds": runtime["sessions"][0]["last_ack_age_seconds"],
        }
    ]


def test_auto_accept_binds_sessions_and_chunks_to_channel() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
    )
    iface = _make_iface()

    service.on_receive(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64", channel=2),
        iface,
    )
    now["value"] = 10.1
    service.on_receive(
        _packet("MF_FILE_V2|C|abcd1234|0|AQID", channel=3),
        iface,
    )
    now["value"] = 10.2
    service.on_receive(
        _packet("MF_FILE_V2|C|abcd1234|0|AQID", channel=2),
        iface,
    )

    assert [row["channel_index"] for row in sent_messages] == [2, 2]
    runtime = service.get_runtime()
    assert runtime["active_sessions"] == 1
    assert runtime["sessions"][0]["key"] == "!01020304|!12345678|abcd1234|2"
    assert runtime["sessions"][0]["received_chunks"] == 1


def test_auto_accept_suppresses_exact_packet_replays_with_fingerprint_fallback() -> None:
    for packet_id in (None, 0, True, 77):
        sent_messages: list[dict[str, object]] = []
        now = {"value": 10.0}
        service = build_file_transfer_auto_accept_service(
            local_node_id_fn=lambda: "!12345678",
            send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
            now_monotonic_fn=lambda: now["value"],
            ack_cooldown_seconds=0,
        )
        iface = _make_iface()
        meta = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
        chunk = _packet("MF_FILE_V2|C|abcd1234|0|AQID")
        if packet_id is not None:
            meta["id"] = packet_id - 1 if packet_id > 1 else packet_id
            chunk["id"] = packet_id

        service.on_receive(meta, iface)
        now["value"] = 10.1
        service.on_receive(chunk, iface)
        now["value"] = 10.2
        service.on_receive(dict(chunk), iface)

        assert len(sent_messages) == 2
        assert service.get_runtime()["sent_ack_count"] == 2


def test_auto_accept_allows_idless_retransmit_after_short_fallback_ttl() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
        replay_ttl_seconds=600,
        replay_fallback_ttl_seconds=5,
    )
    iface = _make_iface()
    meta = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    chunk = _packet("MF_FILE_V2|C|abcd1234|0|AQID")

    service.on_receive(meta, iface)
    now["value"] = 10.1
    service.on_receive(chunk, iface)
    now["value"] = 10.2
    service.on_receive(dict(chunk), iface)
    now["value"] = 16.0
    service.on_receive(dict(chunk), iface)

    assert len(sent_messages) == 3
    assert service.get_runtime()["sent_ack_count"] == 3


def test_auto_accept_keeps_stable_packet_ids_on_long_replay_ttl() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=0,
        replay_ttl_seconds=600,
        replay_fallback_ttl_seconds=5,
    )
    iface = _make_iface()
    meta = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    meta["id"] = 41
    chunk = _packet("MF_FILE_V2|C|abcd1234|0|AQID")
    chunk["id"] = 42

    service.on_receive(meta, iface)
    now["value"] = 10.1
    service.on_receive(chunk, iface)
    now["value"] = 16.0
    service.on_receive(dict(chunk), iface)

    assert len(sent_messages) == 2
    assert service.get_runtime()["sent_ack_count"] == 2


def test_auto_accept_rate_limits_repeated_final_chunks_with_new_packet_ids() -> None:
    sent_messages: list[dict[str, object]] = []
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        ack_cooldown_seconds=1.0,
    )
    iface = _make_iface()
    meta = _packet("MF_FILE_V2|M|abcd1234|sample.bin|64|1|raw|64")
    meta["id"] = 1
    chunk = _packet("MF_FILE_V2|C|abcd1234|0|AQID")

    service.on_receive(meta, iface)
    now["value"] = 10.1
    chunk["id"] = 2
    service.on_receive(dict(chunk), iface)
    now["value"] = 10.2
    chunk["id"] = 3
    service.on_receive(dict(chunk), iface)
    now["value"] = 11.2
    chunk["id"] = 4
    service.on_receive(dict(chunk), iface)

    assert len(sent_messages) == 3
    assert service.get_runtime()["sent_ack_count"] == 3


def test_auto_accept_enforces_exact_session_limit() -> None:
    now = {"value": 10.0}
    service = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **_kwargs: {"ok": True},
        now_monotonic_fn=lambda: now["value"],
        max_sessions=2,
        meta_peer_cooldown_seconds=0.0,
        meta_global_cooldown_seconds=0.0,
    )
    iface = _make_iface()

    for index, transfer_id in enumerate(("abcd0001", "abcd0002", "abcd0003")):
        now["value"] = 10.0 + index
        service.on_receive(
            _packet(
                f"MF_FILE_V2|M|{transfer_id}|sample.bin|64|1|raw|64",
                channel=2,
            ),
            iface,
        )

    runtime = service.get_runtime()
    assert runtime["active_sessions"] == 2
    assert {
        row["transfer_id"] for row in runtime["sessions"]
    } == {"abcd0002", "abcd0003"}


def test_auto_accept_ignores_disabled_and_broadcast_transfers() -> None:
    sent_messages: list[dict[str, object]] = []
    disabled = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
        enabled=False,
    )
    enabled = build_file_transfer_auto_accept_service(
        local_node_id_fn=lambda: "!12345678",
        send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
    )

    disabled.on_receive(
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320"),
        _make_iface(),
    )
    enabled.on_receive(
        _packet(
            "MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320",
            to_num=0xFFFFFFFF,
        ),
        _make_iface(),
    )

    assert sent_messages == []


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
                "enabled": True,
                "active_sessions": 1,
                "sessions": [
                    {
                        "key": "!01020304|!12345678|abcd1234|2",
                        "transfer_id": "abcd1234",
                        "received_chunks": 1,
                        "total_chunks": 2,
                    }
                ],
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

    assert payload.summary["file_transfer"] == {
        "ok": True,
        "enabled": True,
        "active_sessions": 1,
        "sessions": [
            {
                "key": "!01020304|!12345678|abcd1234|2",
                "transfer_id": "abcd1234",
                "received_chunks": 1,
                "total_chunks": 2,
            }
        ],
    }


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


def test_runtime_wires_backend_auto_accept_when_enabled(tmp_path) -> None:
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
        file_transfer_enable=True,
        file_transfer_auto_accept=True,
        file_transfer_max_bytes=1024,
    )

    def _loaders(**_kwargs: object) -> DashboardRuntimeLoaders:
        def _state() -> dict[str, object]:
            return {}

        return DashboardRuntimeLoaders(
            state_fn=_state,
            node_history_fn=lambda *_args, **_kwargs: {},
            online_activity_fn=lambda *_args, **_kwargs: {},
            summary_metrics_fn=lambda *_args, **_kwargs: {},
            send_chat_fn=lambda **kwargs: sent_messages.append(dict(kwargs)) or {"ok": True},
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
        build_online_activity_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_summary_metrics_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        build_send_chat_loader_fn=lambda *_args, **_kwargs: lambda **_kw: {},
        default_chat_max_bytes=200,
        build_dashboard_runtime_loaders_fn=_loaders,
    )

    service_callbacks = [
        callback
        for callback, topic in subscriptions
        if topic == "meshtastic.receive"
        and getattr(getattr(callback, "__self__", None), "__class__", None).__name__
        == "FileTransferAutoAcceptService"
    ]
    assert len(service_callbacks) == 1
    assert callable(getattr(context.tracker, "get_file_transfer_runtime", None))

    service_callbacks[0](
        _packet("MF_FILE_V2|M|abcd1234|sample.bin|320|2|raw|320"),
        iface,
    )
    service_callbacks[0](
        _packet("MF_FILE_V2|M|abcd5678|sample.bin|1025|7|raw|1025"),
        iface,
    )

    assert sent_messages == [
        {
            "text": "MF_FILE_V2|A|abcd1234|0|2|AA==",
            "destination": "!01020304",
            "channel_index": 2,
        }
    ]
