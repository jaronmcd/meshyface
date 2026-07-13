from __future__ import annotations

import threading
from collections import Counter
from pathlib import Path

import pytest

from meshdash.file_transfer_protocol import (
    build_file_transfer_ack_frame,
    file_transfer_frame_text,
    parse_file_transfer_frame_text,
)
from meshdash.services_file_transfer_outbound import (
    ApprovedPathFileResolver,
    OutboundFileTransferService,
    ResolvedOutboundFile,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        delay = max(0.0, float(seconds))
        self.sleeps.append(delay)
        self.now += delay


class _StaticResolver:
    def __init__(self, data: bytes, *, name: str = "sample.bin") -> None:
        self.data = data
        self.name = name
        self.calls: list[str] = []

    def resolve(self, reference: str) -> ResolvedOutboundFile:
        self.calls.append(reference)
        return ResolvedOutboundFile(
            file_name=self.name,
            data=self.data,
            source=f"fixture:{reference}",
        )


def _ack(
    transfer_id: str,
    total_chunks: int,
    received_indexes: object,
) -> str:
    frame = build_file_transfer_ack_frame(
        transfer_id=transfer_id,
        total_chunks=total_chunks,
        received_indexes=received_indexes,
    )
    assert frame
    return frame


def test_approved_path_file_resolver_allows_roots_and_ids_and_blocks_escape(
    tmp_path: Path,
) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    direct = approved / "direct.bin"
    direct.write_bytes(b"direct")
    mapped = approved / "mapped.bin"
    mapped.write_bytes(b"mapped")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    escape = approved / "escape.bin"
    escape.symlink_to(outside)

    resolver = ApprovedPathFileResolver(
        approved,
        file_ids={"welcome": mapped},
        max_file_bytes=16,
    )

    assert resolver.resolve("direct.bin").data == b"direct"
    resolved_id = resolver.resolve("welcome")
    assert resolved_id.file_name == "mapped.bin"
    assert resolved_id.data == b"mapped"

    with pytest.raises(ValueError, match="outside the approved"):
        resolver.resolve(str(outside))
    with pytest.raises(ValueError, match="outside the approved"):
        resolver.resolve(str(escape))

    empty = approved / "empty.bin"
    empty.touch()
    with pytest.raises(ValueError, match="empty"):
        resolver.resolve(str(empty))

    oversized = approved / "oversized.bin"
    oversized.write_bytes(b"x" * 17)
    with pytest.raises(ValueError, match="16-byte"):
        resolver.resolve(str(oversized))


def test_submit_is_bounded_nonblocking_and_defers_resolution() -> None:
    resolver = _StaticResolver(b"payload")
    transfer_ids = iter(("abcd0001", "abcd0002"))
    service = OutboundFileTransferService(
        file_resolver=resolver,
        send_frame_fn=lambda **_kwargs: {"ok": True},
        queue_capacity=1,
        transfer_id_fn=lambda: next(transfer_ids),
        autostart=False,
    )

    first = service.submit(
        destination_id="!aabbccdd",
        path_or_file_id="approved-id",
        channel_index=2,
    )
    full = service.submit(
        destination_id="!11223344",
        path_or_file_id="second-id",
    )
    invalid = service.submit(
        destination_id="^all",
        path_or_file_id="approved-id",
    )

    assert first == {
        "ok": True,
        "accepted": True,
        "job_id": "abcd0001",
        "transfer_id": "abcd0001",
        "status": "queued",
    }
    assert full == {
        "ok": False,
        "accepted": False,
        "error": "Outbound file transfer queue is full",
    }
    assert invalid["accepted"] is False
    assert resolver.calls == []
    assert service.get_status()["queued_jobs"] == 1
    assert service.get_status()["rejected_count"] == 2

    service.close()
    assert service.get_job("abcd0001")["status"] == "canceled"  # type: ignore[index]


def test_transfer_chunks_paces_and_completes_through_chat_send_path() -> None:
    clock = _FakeClock()
    sent: list[dict[str, object]] = []
    progress: list[dict[str, object]] = []
    service: OutboundFileTransferService

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        sent.append({**kwargs, "frame": parsed})
        if parsed["kind"] == "meta":
            assert service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("abcd1234", 3, ()),
                channel_index=4,
            )
        elif parsed["kind"] == "chunk" and parsed["chunk_index"] == 2:
            assert service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("abcd1234", 3, range(3)),
                channel_index=4,
            )
        return {"ok": True}

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"x" * 330),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0.25,
        ack_timeout_seconds=1.0,
        ack_poll_seconds=0.1,
        max_retries=1,
        progress_fn=lambda event: progress.append(event),
        clock_fn=clock,
        sleep_fn=clock.sleep,
        transfer_id_fn=lambda: "abcd1234",
        autostart=False,
    )
    submitted = service.submit(
        destination_id="!aabbccdd",
        path_or_file_id="fixture",
        channel_index=1,
    )

    assert submitted["accepted"] is True
    assert service.run_pending_once() is True
    assert service.run_pending_once() is False

    frames = [entry["frame"] for entry in sent]
    assert [frame["kind"] for frame in frames] == ["meta", "chunk", "chunk", "chunk"]  # type: ignore[index]
    assert [frame["chunk_index"] for frame in frames[1:]] == [0, 1, 2]  # type: ignore[index]
    assert [entry["destination"] for entry in sent] == ["!aabbccdd"] * 4
    assert [entry["channel_index"] for entry in sent] == [1, 4, 4, 4]
    assert clock.sleeps == [0.25, 0.25, 0.25]

    job = service.get_job("abcd1234")
    assert job is not None
    assert job["status"] == "completed"
    assert job["file_size"] == 330
    assert job["total_chunks"] == 3
    assert job["acked_chunks"] == 3
    assert job["sent_chunks"] == 3
    assert [event["event"] for event in progress][-1] == "completed"
    status = service.get_status()
    assert status["completed_count"] == 1
    assert status["sent_frame_count"] == 4


def test_partial_ack_retries_only_missing_chunks() -> None:
    clock = _FakeClock()
    sent_chunk_indexes: list[int] = []
    sends_by_chunk: Counter[int] = Counter()
    duplicate_ack_count = 0
    service: OutboundFileTransferService

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        if parsed["kind"] == "meta":
            assert service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("face0001", 3, ()),
            )
        elif parsed["kind"] == "chunk":
            index = int(parsed["chunk_index"])
            sent_chunk_indexes.append(index)
            sends_by_chunk[index] += 1
            if index == 2 and sends_by_chunk[index] == 1:
                assert service.handle_ack(
                    sender_id="!aabbccdd",
                    frame=_ack("face0001", 3, (0,)),
                )
            elif index == 2 and sends_by_chunk[index] == 2:
                assert service.handle_ack(
                    sender_id="!aabbccdd",
                    frame=_ack("face0001", 3, range(3)),
                )
        return {"ok": True}

    def _sleep_with_duplicate_ack(seconds: float) -> None:
        nonlocal duplicate_ack_count
        clock.sleep(seconds)
        if duplicate_ack_count >= 3:
            return
        duplicate_ack_count += 1
        assert service.handle_ack(
            sender_id="!aabbccdd",
            frame=_ack("face0001", 3, (0,)),
        )

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"z" * 330),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0,
        ack_timeout_seconds=1,
        ack_poll_seconds=0.25,
        max_retries=1,
        clock_fn=clock,
        sleep_fn=_sleep_with_duplicate_ack,
        transfer_id_fn=lambda: "face0001",
        autostart=False,
    )
    service.submit(destination_id="!aabbccdd", path_or_file_id="fixture")

    assert service.run_pending_once() is True
    assert sent_chunk_indexes == [0, 1, 2, 1, 2]
    assert sum(clock.sleeps) == 1.0
    assert duplicate_ack_count == 3
    job = service.get_job("face0001")
    assert job is not None
    assert job["status"] == "completed"
    assert job["retry_count"] == 1
    assert service.get_status()["retry_frame_count"] == 2


def test_metadata_timeout_retries_then_marks_job_failed() -> None:
    clock = _FakeClock()
    sent_kinds: list[str] = []

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        sent_kinds.append(str(parsed["kind"]))
        return {"ok": True}

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"payload"),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0,
        ack_timeout_seconds=1,
        ack_poll_seconds=0.25,
        max_retries=1,
        clock_fn=clock,
        sleep_fn=clock.sleep,
        transfer_id_fn=lambda: "dead0001",
        autostart=False,
    )
    service.submit(destination_id="!aabbccdd", path_or_file_id="fixture")

    assert service.run_pending_once() is True
    assert sent_kinds == ["meta", "meta"]
    assert sum(clock.sleeps) == 2.0
    job = service.get_job("dead0001")
    assert job is not None
    assert job["status"] == "failed"
    assert "acceptance" in str(job["error"])
    assert job["retry_count"] == 1


def test_host_cancel_stops_active_transfer_and_sends_cancel_flow() -> None:
    sent_kinds: list[str] = []
    service: OutboundFileTransferService

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        sent_kinds.append(str(parsed["kind"]))
        if parsed["kind"] == "meta":
            assert service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("cafe0001", 2, ()),
            )
        elif parsed["kind"] == "chunk":
            assert service.cancel("cafe0001") is True
        return {"ok": True}

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"c" * 200),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0,
        ack_timeout_seconds=1,
        max_retries=1,
        transfer_id_fn=lambda: "cafe0001",
        autostart=False,
    )
    service.submit(destination_id="!aabbccdd", path_or_file_id="fixture")

    assert service.run_pending_once() is True
    assert sent_kinds == ["meta", "chunk", "flow"]
    job = service.get_job("cafe0001")
    assert job is not None
    assert job["status"] == "canceled"
    assert job["sent_chunks"] == 1
    assert service.cancel("cafe0001") is False


def test_peer_cancel_is_accepted_without_echoing_cancel() -> None:
    sent_kinds: list[str] = []
    service: OutboundFileTransferService

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        sent_kinds.append(str(parsed["kind"]))
        if parsed["kind"] == "meta":
            assert service.handle_flow(
                sender_id="!aabbccdd",
                frame=file_transfer_frame_text(
                    {
                        "kind": "flow",
                        "transfer_id": "beef0001",
                        "action": "cancel",
                    }
                ),
            )
        return {"ok": True}

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"payload"),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0,
        ack_timeout_seconds=1,
        max_retries=1,
        transfer_id_fn=lambda: "beef0001",
        autostart=False,
    )
    service.submit(destination_id="!aabbccdd", path_or_file_id="fixture")

    assert service.run_pending_once() is True
    assert sent_kinds == ["meta"]
    assert service.get_job("beef0001")["status"] == "canceled"  # type: ignore[index]


def test_close_is_idempotent_and_leaves_no_worker_or_queued_job() -> None:
    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"payload"),
        send_frame_fn=lambda **_kwargs: {"ok": True},
        autostart=True,
    )

    service.close(timeout=1)
    service.close(timeout=1)

    status = service.get_status()
    assert status["accepting"] is False
    assert status["worker_running"] is False
    assert status["thread_alive"] is False
    assert status["queued_jobs"] == 0
    rejected = service.submit(
        destination_id="!aabbccdd",
        path_or_file_id="fixture",
    )
    assert rejected == {
        "ok": False,
        "accepted": False,
        "error": "Outbound file transfer service is closed",
    }


def test_background_worker_processes_job_and_reports_completion() -> None:
    completed = threading.Event()
    service: OutboundFileTransferService

    def _progress(event: dict[str, object]) -> None:
        if event.get("event") == "completed":
            completed.set()

    def _send_frame(**kwargs: object) -> dict[str, object]:
        parsed = parse_file_transfer_frame_text(kwargs["text"])
        assert parsed is not None
        if parsed["kind"] == "meta":
            service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("feed0001", 1, ()),
            )
        elif parsed["kind"] == "chunk":
            service.handle_ack(
                sender_id="!aabbccdd",
                frame=_ack("feed0001", 1, (0,)),
            )
        return {"ok": True}

    service = OutboundFileTransferService(
        file_resolver=_StaticResolver(b"payload"),
        send_frame_fn=_send_frame,
        frame_pace_seconds=0,
        ack_timeout_seconds=0.1,
        ack_poll_seconds=0.01,
        progress_fn=_progress,
        transfer_id_fn=lambda: "feed0001",
        autostart=True,
    )
    try:
        submitted = service.submit(
            destination_id="!aabbccdd",
            path_or_file_id="fixture",
        )
        assert submitted["accepted"] is True
        assert completed.wait(timeout=1)
        assert service.get_job("feed0001")["status"] == "completed"  # type: ignore[index]
    finally:
        service.close(timeout=1)

    assert service.get_status()["thread_alive"] is False
