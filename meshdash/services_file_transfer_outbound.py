from __future__ import annotations

import base64
import os
import queue
import re
import secrets
import stat
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .file_transfer_protocol import (
    FILE_TRANSFER_CHUNK_BYTES,
    FILE_TRANSFER_MAX_FILE_BYTES,
    FILE_TRANSFER_MAX_WIRE_BYTES,
    encode_file_transfer_frame,
    file_transfer_frame_text,
    parse_file_transfer_frame_text,
)


_CANONICAL_NODE_ID_RE = re.compile(r"^![0-9a-f]{8}$")
_TRANSFER_ID_RE = re.compile(r"^[a-z0-9]{4,24}$")
_TERMINAL_STATES = {"completed", "failed", "canceled"}


@dataclass(frozen=True)
class ResolvedOutboundFile:
    file_name: str
    data: bytes
    source: str = ""


class OutboundFileResolver(Protocol):
    def resolve(self, path_or_file_id: str) -> ResolvedOutboundFile:
        ...


class ApprovedPathFileResolver:
    """Resolve only regular files contained by administrator-approved roots."""

    def __init__(
        self,
        approved_roots: object,
        *,
        file_ids: Mapping[str, object] | None = None,
        max_file_bytes: int = FILE_TRANSFER_MAX_FILE_BYTES,
    ) -> None:
        if isinstance(approved_roots, (str, os.PathLike)):
            root_values = [approved_roots]
        else:
            try:
                root_values = list(approved_roots)  # type: ignore[arg-type]
            except TypeError as exc:
                raise ValueError("At least one approved file root is required") from exc
        roots = tuple(
            Path(str(value)).expanduser().resolve(strict=False)
            for value in root_values
            if str(value or "").strip()
        )
        if not roots:
            raise ValueError("At least one approved file root is required")
        self._approved_roots = roots
        self._file_ids = {
            str(file_id).strip(): Path(str(path)).expanduser()
            for file_id, path in dict(file_ids or {}).items()
            if str(file_id or "").strip() and str(path or "").strip()
        }
        self._max_file_bytes = max(
            1,
            min(FILE_TRANSFER_MAX_FILE_BYTES, int(max_file_bytes)),
        )

    @property
    def approved_roots(self) -> tuple[Path, ...]:
        return self._approved_roots

    def _candidate_path(self, path_or_file_id: str) -> tuple[Path, Path]:
        clean_reference = str(path_or_file_id or "").strip()
        if not clean_reference:
            raise ValueError("A file path or approved file ID is required")
        candidate = self._file_ids.get(clean_reference)
        if candidate is None:
            candidate = Path(clean_reference).expanduser()
        if not candidate.is_absolute():
            candidate = self._approved_roots[0] / candidate
        candidate = Path(os.path.abspath(candidate))
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("Requested file does not exist") from exc
        root = next(
            (
                approved_root
                for approved_root in self._approved_roots
                if _is_relative_to(resolved, approved_root)
            ),
            None,
        )
        if root is None:
            raise ValueError("Requested file is outside the approved file roots")
        # Opening by path after this check would leave a symlink-swap window.
        # Reject any symlink component and open beneath the approved directory
        # descriptor instead.
        if resolved != candidate:
            raise ValueError("Requested file symlinks are not allowed")
        return candidate, root

    def resolve(self, path_or_file_id: str) -> ResolvedOutboundFile:
        candidate, root = self._candidate_path(path_or_file_id)
        descriptor = -1
        try:
            descriptor = _open_regular_file_beneath(candidate, root)
            before = os.fstat(descriptor)
        except OSError as exc:
            raise ValueError("Requested file is not readable") from exc
        if not stat.S_ISREG(before.st_mode):
            if descriptor >= 0:
                os.close(descriptor)
            raise ValueError("Requested file is not a regular file")
        size = int(before.st_size)
        if size <= 0:
            os.close(descriptor)
            raise ValueError("Requested file is empty")
        if size > self._max_file_bytes:
            os.close(descriptor)
            raise ValueError(
                f"Requested file exceeds the {self._max_file_bytes}-byte transfer limit"
            )
        try:
            data = _read_bounded_descriptor(descriptor, self._max_file_bytes)
            after = os.fstat(descriptor)
        except OSError as exc:
            raise ValueError("Requested file is not readable") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if not data:
            raise ValueError("Requested file is empty")
        if len(data) > self._max_file_bytes:
            raise ValueError(
                f"Requested file exceeds the {self._max_file_bytes}-byte transfer limit"
            )
        if (
            len(data) != size
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
            or after.st_ino != before.st_ino
            or after.st_dev != before.st_dev
        ):
            raise ValueError("Requested file changed while it was being read")
        return ResolvedOutboundFile(
            file_name=candidate.name,
            data=data,
            source=str(candidate),
        )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _open_regular_file_beneath(candidate: Path, root: Path) -> int:
    """Open ``candidate`` without following symlinks below ``root``."""

    relative = candidate.relative_to(root)
    parts = relative.parts
    if not parts:
        raise OSError("approved root is not a file")
    close_on_exec = int(getattr(os, "O_CLOEXEC", 0))
    no_follow = int(getattr(os, "O_NOFOLLOW", 0))
    nonblocking = int(getattr(os, "O_NONBLOCK", 0))
    directory_flag = int(getattr(os, "O_DIRECTORY", 0))
    root_fd = os.open(
        root,
        os.O_RDONLY | close_on_exec | no_follow | directory_flag,
    )
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | close_on_exec | no_follow | directory_flag,
                dir_fd=current_fd,
            )
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(
            parts[-1],
            os.O_RDONLY | close_on_exec | no_follow | nonblocking,
            dir_fd=current_fd,
        )
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)
    return descriptor


def _read_bounded_descriptor(descriptor: int, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    remaining = max(1, int(maximum_bytes)) + 1
    while remaining > 0:
        chunk = os.read(descriptor, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


@dataclass
class _OutboundTransferJob:
    job_id: str
    transfer_id: str
    destination_id: str
    channel_index: int
    local_node_id: str
    source_reference: str
    submitted_at: float
    updated_at: float
    status: str = "queued"
    error: str = ""
    file_name: str = ""
    file_size: int = 0
    total_chunks: int = 0
    sent_frames: int = 0
    sent_chunks: int = 0
    retry_count: int = 0
    ack_count: int = 0
    acked_chunks: int = 0
    acked_indexes: set[int] = field(default_factory=set)
    ack_sequence: int = 0
    metadata_accepted: bool = False
    completed_ack: bool = False
    cancel_requested: bool = False
    notify_cancel: bool = False
    metadata_sent: bool = False
    admitted_frames: int | None = None


class _TransferCanceled(RuntimeError):
    pass


class OutboundFileTransferService:
    """Bounded host-managed MF_FILE_V2 sender using the normal chat send path."""

    def __init__(
        self,
        *,
        file_resolver: OutboundFileResolver | Callable[[str], ResolvedOutboundFile],
        send_frame_fn: Callable[..., object],
        queue_capacity: int = 8,
        max_file_bytes: int = FILE_TRANSFER_MAX_FILE_BYTES,
        frame_pace_seconds: float = 0.25,
        ack_timeout_seconds: float = 15.0,
        ack_poll_seconds: float = 0.1,
        max_retries: int = 3,
        progress_fn: Callable[[dict[str, object]], object] | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], object] = time.sleep,
        transfer_id_fn: Callable[[], str] | None = None,
        autostart: bool = True,
        max_history: int = 64,
    ) -> None:
        self._file_resolver = file_resolver
        self._send_frame_fn = send_frame_fn
        self._queue_capacity = max(1, int(queue_capacity))
        self._max_file_bytes = max(
            1,
            min(FILE_TRANSFER_MAX_FILE_BYTES, int(max_file_bytes)),
        )
        self._frame_pace_seconds = max(0.0, float(frame_pace_seconds))
        self._ack_timeout_seconds = max(0.0, float(ack_timeout_seconds))
        self._ack_poll_seconds = max(0.001, float(ack_poll_seconds))
        self._max_retries = max(0, int(max_retries))
        self._progress_fn = progress_fn
        self._clock_fn = clock_fn
        self._sleep_fn = sleep_fn
        self._transfer_id_fn = transfer_id_fn or (lambda: secrets.token_hex(6))
        self._max_history = max(1, int(max_history))
        self._queue: queue.Queue[str] = queue.Queue(maxsize=self._queue_capacity)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._jobs: dict[str, _OutboundTransferJob] = {}
        self._job_order: list[str] = []
        self._active_job_id = ""
        self._accepting = True
        self._worker_running = False
        self._thread: threading.Thread | None = None
        self._submitted_count = 0
        self._rejected_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self._canceled_count = 0
        self._sent_frame_count = 0
        self._retry_frame_count = 0
        self._ack_count = 0
        if autostart:
            self.start()

    def start(self) -> None:
        with self._lock:
            if not self._accepting:
                raise RuntimeError("Outbound file transfer service is closed")
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._worker_loop,
                name="meshyface-file-transfer-outbound",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def submit(
        self,
        *,
        destination_id: object,
        path_or_file_id: object,
        channel_index: object = 0,
        local_node_id: object = None,
        admitted_frames: object = None,
    ) -> dict[str, object]:
        destination = _canonical_direct_node_id(destination_id)
        local_node = (
            _canonical_direct_node_id(local_node_id)
            if local_node_id is not None
            else ""
        )
        source_reference = str(path_or_file_id or "").strip()
        channel = _channel_index(channel_index)
        frame_limit = (
            _positive_int(admitted_frames)
            if admitted_frames is not None
            else None
        )
        if not destination:
            return self._reject("A canonical direct destination is required")
        if local_node_id is not None and not local_node:
            return self._reject("A canonical local node ID is required")
        if not source_reference:
            return self._reject("A file path or approved file ID is required")
        if channel is None:
            return self._reject("Channel index must be an integer from 0 through 7")
        if admitted_frames is not None and frame_limit is None:
            return self._reject("Admitted frame count must be a positive integer")
        with self._lock:
            if not self._accepting:
                return self._reject_locked("Outbound file transfer service is closed")
            try:
                transfer_id = self._new_transfer_id()
            except RuntimeError as exc:
                return self._reject_locked(str(exc))
            now = float(self._clock_fn())
            job = _OutboundTransferJob(
                job_id=transfer_id,
                transfer_id=transfer_id,
                destination_id=destination,
                channel_index=channel,
                local_node_id=local_node,
                source_reference=source_reference,
                submitted_at=now,
                updated_at=now,
                admitted_frames=frame_limit,
            )
            self._jobs[job.job_id] = job
            self._job_order.append(job.job_id)
            try:
                self._queue.put_nowait(job.job_id)
            except queue.Full:
                self._jobs.pop(job.job_id, None)
                self._job_order.remove(job.job_id)
                return self._reject_locked("Outbound file transfer queue is full")
            self._submitted_count += 1
        self._emit(job, "queued")
        return {
            "ok": True,
            "accepted": True,
            "job_id": job.job_id,
            "transfer_id": job.transfer_id,
            "status": job.status,
        }

    def estimate_transfer_cost(self, path_or_file_id: object) -> dict[str, int]:
        """Return a conservative initial-send radio cost for one approved file."""

        source_reference = str(path_or_file_id or "").strip()
        if not source_reference:
            raise ValueError("A file path or approved file ID is required")
        resolved = self._resolve_file(source_reference)
        size = len(resolved.data)
        if size <= 0:
            raise ValueError("Requested file is empty")
        if size > self._max_file_bytes:
            raise ValueError(
                f"Requested file exceeds the {self._max_file_bytes}-byte transfer limit"
            )
        chunks = (size + FILE_TRANSFER_CHUNK_BYTES - 1) // FILE_TRANSFER_CHUNK_BYTES
        # Metadata and every missing chunk may be sent once initially and once
        # per retry round. Reserve that full upper bound before admitting the
        # plugin action.
        frames = (1 + chunks) * (self._max_retries + 1)
        return {
            "frames": frames,
            # Charge the maximum protocol payload for every frame so metadata
            # and encoding overhead cannot make the admission estimate too low.
            "bytes": frames * FILE_TRANSFER_MAX_WIRE_BYTES,
            "file_bytes": size,
        }

    def _reject(self, error: str) -> dict[str, object]:
        with self._lock:
            return self._reject_locked(error)

    def _reject_locked(self, error: str) -> dict[str, object]:
        self._rejected_count += 1
        return {"ok": False, "accepted": False, "error": error}

    def _new_transfer_id(self) -> str:
        for _attempt in range(8):
            candidate = str(self._transfer_id_fn() or "").strip().lower()
            if not _TRANSFER_ID_RE.fullmatch(candidate):
                raise RuntimeError("Transfer ID generator returned an invalid ID")
            with self._lock:
                if candidate not in self._jobs:
                    return candidate
        raise RuntimeError("Unable to allocate a unique transfer ID")

    def run_pending_once(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Cannot manually drain a running outbound worker")
        try:
            job_id = self._queue.get_nowait()
        except queue.Empty:
            return False
        try:
            self._process_job_id(job_id)
        finally:
            self._queue.task_done()
        return True

    def handle_ack(
        self,
        *,
        sender_id: object,
        frame: object,
        channel_index: object = None,
        destination_id: object = None,
    ) -> bool:
        parsed = _parse_frame(frame, max_file_bytes=self._max_file_bytes)
        if parsed is None or parsed.get("kind") != "ack":
            return False
        sender = _canonical_direct_node_id(sender_id)
        transfer_id = str(parsed.get("transfer_id") or "").strip().lower()
        channel = _channel_index(channel_index)
        destination = (
            _canonical_direct_node_id(destination_id)
            if destination_id is not None
            else None
        )
        progress_payload: tuple[_OutboundTransferJob, int, bool] | None = None
        with self._lock:
            job = self._jobs.get(transfer_id)
            if (
                job is None
                or job.status in _TERMINAL_STATES
                or sender != job.destination_id
                or channel is None
                or channel != job.channel_index
                or (
                    destination_id is not None
                    and (not destination or destination != job.local_node_id)
                )
                or int(parsed.get("total_chunks") or 0) != job.total_chunks
            ):
                return False
            prior_metadata_accepted = job.metadata_accepted
            prior_acked_chunks = job.acked_chunks
            prior_completed_ack = job.completed_ack
            bitmap = parsed.get("bitmap_bytes")
            indexes = _bitmap_indexes(bitmap, total_chunks=job.total_chunks)
            received_count = max(0, int(parsed.get("received_count") or 0))
            job.acked_indexes.update(indexes)
            job.acked_chunks = min(
                job.total_chunks,
                max(job.acked_chunks, received_count, len(job.acked_indexes)),
            )
            job.metadata_accepted = True
            job.completed_ack = (
                received_count >= job.total_chunks
                or len(job.acked_indexes) >= job.total_chunks
            )
            if job.completed_ack:
                job.acked_indexes = set(range(job.total_chunks))
                job.acked_chunks = job.total_chunks
            job.ack_count += 1
            made_progress = (
                not prior_metadata_accepted
                or job.acked_chunks > prior_acked_chunks
                or (job.completed_ack and not prior_completed_ack)
            )
            if made_progress:
                job.ack_sequence += 1
            job.updated_at = float(self._clock_fn())
            self._ack_count += 1
            progress_payload = (job, job.acked_chunks, made_progress)
        if progress_payload is not None:
            progress_job, acked_chunks, made_progress = progress_payload
            self._emit(
                progress_job,
                "ack",
                acked_chunks=acked_chunks,
                complete=progress_job.completed_ack,
                made_progress=made_progress,
            )
        return True

    def handle_flow(
        self,
        *,
        sender_id: object,
        frame: object,
        channel_index: object = None,
        destination_id: object = None,
    ) -> bool:
        parsed = _parse_frame(frame, max_file_bytes=self._max_file_bytes)
        if (
            parsed is None
            or parsed.get("kind") != "flow"
            or parsed.get("action") != "cancel"
        ):
            return False
        sender = _canonical_direct_node_id(sender_id)
        transfer_id = str(parsed.get("transfer_id") or "").strip().lower()
        channel = _channel_index(channel_index)
        destination = (
            _canonical_direct_node_id(destination_id)
            if destination_id is not None
            else None
        )
        with self._lock:
            job = self._jobs.get(transfer_id)
            if (
                job is None
                or job.status in _TERMINAL_STATES
                or sender != job.destination_id
                or channel is None
                or channel != job.channel_index
                or (
                    destination_id is not None
                    and (not destination or destination != job.local_node_id)
                )
            ):
                return False
            job.cancel_requested = True
            job.notify_cancel = False
            job.updated_at = float(self._clock_fn())
        self._emit(job, "cancel_requested", source="peer")
        return True

    def cancel(self, job_or_transfer_id: object) -> bool:
        clean_id = str(job_or_transfer_id or "").strip().lower()
        with self._lock:
            job = self._jobs.get(clean_id)
            if job is None or job.status in _TERMINAL_STATES:
                return False
            job.cancel_requested = True
            job.notify_cancel = bool(job.metadata_sent)
            job.updated_at = float(self._clock_fn())
        self._emit(job, "cancel_requested", source="host")
        return True

    def get_job(self, job_or_transfer_id: object) -> dict[str, object] | None:
        clean_id = str(job_or_transfer_id or "").strip().lower()
        with self._lock:
            job = self._jobs.get(clean_id)
            return self._job_snapshot_locked(job) if job is not None else None

    def get_status(self) -> dict[str, object]:
        with self._lock:
            thread_alive = bool(self._thread is not None and self._thread.is_alive())
            return {
                "accepting": bool(self._accepting),
                "worker_running": bool(self._worker_running and thread_alive),
                "thread_alive": thread_alive,
                "queue_capacity": self._queue_capacity,
                "queued_jobs": self._queue.qsize(),
                "active_job_id": self._active_job_id or None,
                "submitted_count": self._submitted_count,
                "rejected_count": self._rejected_count,
                "completed_count": self._completed_count,
                "failed_count": self._failed_count,
                "canceled_count": self._canceled_count,
                "sent_frame_count": self._sent_frame_count,
                "retry_frame_count": self._retry_frame_count,
                "ack_count": self._ack_count,
                "jobs": [
                    self._job_snapshot_locked(self._jobs[job_id])
                    for job_id in self._job_order
                    if job_id in self._jobs
                ],
            }

    def close(self, *, timeout: float = 2.0) -> None:
        with self._lock:
            if not self._accepting and self._stop_event.is_set():
                thread = self._thread
            else:
                self._accepting = False
                self._stop_event.set()
                active = self._jobs.get(self._active_job_id)
                if active is not None and active.status not in _TERMINAL_STATES:
                    active.cancel_requested = True
                    active.notify_cancel = False
                thread = self._thread

        drained: list[_OutboundTransferJob] = []
        while True:
            try:
                job_id = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                with self._lock:
                    job = self._jobs.get(job_id)
                if job is not None and job.status not in _TERMINAL_STATES:
                    drained.append(job)
            finally:
                self._queue.task_done()
        for job in drained:
            self._mark_terminal(job, "canceled", "Service shut down before transfer started")
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(timeout)))

    def _worker_loop(self) -> None:
        with self._lock:
            self._worker_running = True
        try:
            while not self._stop_event.is_set():
                try:
                    job_id = self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    self._process_job_id(job_id)
                finally:
                    self._queue.task_done()
        finally:
            with self._lock:
                self._worker_running = False
                self._active_job_id = ""

    def _process_job_id(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in _TERMINAL_STATES:
                return
            self._active_job_id = job.job_id
            job.status = "resolving"
            job.updated_at = float(self._clock_fn())
        self._emit(job, "resolving")
        try:
            self._raise_if_canceled(job)
            resolved = self._resolve_file(job.source_reference)
            if not resolved.data:
                raise ValueError("Requested file is empty")
            if len(resolved.data) > self._max_file_bytes:
                raise ValueError(
                    f"Requested file exceeds the {self._max_file_bytes}-byte transfer limit"
                )
            chunks = [
                resolved.data[offset:offset + FILE_TRANSFER_CHUNK_BYTES]
                for offset in range(0, len(resolved.data), FILE_TRANSFER_CHUNK_BYTES)
            ]
            maximum_frames = (1 + len(chunks)) * (self._max_retries + 1)
            if (
                job.admitted_frames is not None
                and maximum_frames > job.admitted_frames
            ):
                raise ValueError("Requested file grew beyond its admitted radio-frame budget")
            with self._lock:
                job.file_name = str(resolved.file_name or "file.bin")
                job.file_size = len(resolved.data)
                job.total_chunks = len(chunks)
                job.status = "sending"
                job.updated_at = float(self._clock_fn())
            metadata = {
                "kind": "meta",
                "transfer_id": job.transfer_id,
                "file_name": job.file_name,
                "file_size": job.file_size,
                "total_chunks": job.total_chunks,
                "codec": "raw",
                "original_file_size": job.file_size,
            }
            chunk_frames = [
                {
                    "kind": "chunk",
                    "transfer_id": job.transfer_id,
                    "chunk_index": index,
                    "chunk_data": base64.b64encode(chunk).decode("ascii"),
                    "chunk_bytes": chunk,
                }
                for index, chunk in enumerate(chunks)
            ]
            self._validate_frames(metadata, chunk_frames)
            self._send_metadata_until_accepted(job, metadata)
            for frame in chunk_frames:
                self._send_frame(job, frame)
            self._wait_for_completion_with_retries(job, chunk_frames)
            self._mark_terminal(job, "completed", "")
        except _TransferCanceled:
            if job.notify_cancel and job.metadata_sent:
                self._send_cancel_notification(job)
            self._mark_terminal(job, "canceled", "Transfer canceled")
        except Exception as exc:
            self._mark_terminal(job, "failed", str(exc) or type(exc).__name__)
        finally:
            with self._lock:
                if self._active_job_id == job.job_id:
                    self._active_job_id = ""

    def _resolve_file(self, source_reference: str) -> ResolvedOutboundFile:
        resolver_fn = getattr(self._file_resolver, "resolve", None)
        if not callable(resolver_fn) and callable(self._file_resolver):
            resolver_fn = self._file_resolver
        if not callable(resolver_fn):
            raise RuntimeError("Outbound file resolver is unavailable")
        resolved = resolver_fn(source_reference)
        if not isinstance(resolved, ResolvedOutboundFile):
            raise TypeError("Outbound file resolver returned an invalid result")
        return resolved

    def _validate_frames(
        self,
        metadata: Mapping[str, object],
        chunks: list[dict[str, object]],
    ) -> None:
        encode_file_transfer_frame(metadata)
        if not file_transfer_frame_text(metadata):
            raise ValueError("Unable to encode MF_FILE_V2 metadata")
        for frame in chunks:
            encode_file_transfer_frame(frame)
            if not file_transfer_frame_text(frame):
                raise ValueError("Unable to encode MF_FILE_V2 chunk")

    def _send_metadata_until_accepted(
        self,
        job: _OutboundTransferJob,
        metadata: Mapping[str, object],
    ) -> None:
        for attempt in range(self._max_retries + 1):
            self._raise_if_canceled(job)
            self._send_frame(job, metadata, retry=attempt > 0)
            with self._lock:
                job.metadata_sent = True
            if self._wait_until(job, lambda: job.metadata_accepted):
                return
            if attempt < self._max_retries:
                with self._lock:
                    job.retry_count += 1
                self._emit(job, "retrying", phase="metadata", attempt=attempt + 1)
        raise TimeoutError("Timed out waiting for file-transfer acceptance")

    def _wait_for_completion_with_retries(
        self,
        job: _OutboundTransferJob,
        chunks: list[dict[str, object]],
    ) -> None:
        retry_round = 0
        while True:
            self._raise_if_canceled(job)
            with self._lock:
                if job.completed_ack:
                    return
                ack_sequence = job.ack_sequence
            progressed = self._wait_until(
                job,
                lambda: job.completed_ack or job.ack_sequence > ack_sequence,
            )
            with self._lock:
                if job.completed_ack:
                    return
            if progressed:
                continue
            if retry_round >= self._max_retries:
                raise TimeoutError("Timed out waiting for file-transfer acknowledgement")
            retry_round += 1
            with self._lock:
                missing_indexes = [
                    index
                    for index in range(job.total_chunks)
                    if index not in job.acked_indexes
                ]
                if not missing_indexes:
                    missing_indexes = list(range(job.total_chunks))
                job.retry_count += 1
            self._emit(
                job,
                "retrying",
                phase="chunks",
                attempt=retry_round,
                missing_indexes=list(missing_indexes),
            )
            for index in missing_indexes:
                self._send_frame(job, chunks[index], retry=True)

    def _wait_until(
        self,
        job: _OutboundTransferJob,
        predicate: Callable[[], bool],
    ) -> bool:
        deadline = float(self._clock_fn()) + self._ack_timeout_seconds
        while True:
            self._raise_if_canceled(job)
            with self._lock:
                if predicate():
                    return True
            remaining = deadline - float(self._clock_fn())
            if remaining <= 0:
                return False
            self._sleep_fn(min(self._ack_poll_seconds, remaining))

    def _send_frame(
        self,
        job: _OutboundTransferJob,
        frame: Mapping[str, object],
        *,
        retry: bool = False,
    ) -> None:
        self._raise_if_canceled(job)
        with self._lock:
            if (
                job.admitted_frames is not None
                and job.sent_frames >= job.admitted_frames
            ):
                raise RuntimeError("File transfer exhausted its admitted radio-frame budget")
            should_pace = job.sent_frames > 0 and self._frame_pace_seconds > 0
        if should_pace:
            self._sleep_fn(self._frame_pace_seconds)
            self._raise_if_canceled(job)
        text = file_transfer_frame_text(frame)
        if not text:
            raise ValueError("Unable to encode MF_FILE_V2 frame")
        response = self._send_frame_fn(
            text=text,
            destination=job.destination_id,
            channel_index=job.channel_index,
        )
        if isinstance(response, Mapping) and response.get("ok") is False:
            raise RuntimeError(str(response.get("error") or "File-transfer frame send failed"))
        kind = str(frame.get("kind") or "")
        with self._lock:
            job.sent_frames += 1
            if kind == "chunk":
                job.sent_chunks += 1
            job.updated_at = float(self._clock_fn())
            self._sent_frame_count += 1
            if retry:
                self._retry_frame_count += 1
        self._emit(
            job,
            "frame_sent",
            frame_kind=kind,
            chunk_index=frame.get("chunk_index"),
            retry=retry,
        )

    def _send_cancel_notification(self, job: _OutboundTransferJob) -> None:
        frame = {
            "kind": "flow",
            "transfer_id": job.transfer_id,
            "action": "cancel",
        }
        try:
            with self._lock:
                if (
                    job.admitted_frames is not None
                    and job.sent_frames >= job.admitted_frames
                ):
                    return
            text = file_transfer_frame_text(frame)
            response = self._send_frame_fn(
                text=text,
                destination=job.destination_id,
                channel_index=job.channel_index,
            )
            if isinstance(response, Mapping) and response.get("ok") is False:
                return
            with self._lock:
                job.sent_frames += 1
                self._sent_frame_count += 1
        except Exception:
            return

    def _raise_if_canceled(self, job: _OutboundTransferJob) -> None:
        with self._lock:
            canceled = job.cancel_requested or self._stop_event.is_set()
        if canceled:
            raise _TransferCanceled()

    def _mark_terminal(
        self,
        job: _OutboundTransferJob,
        status: str,
        error: str,
    ) -> None:
        with self._lock:
            if job.status in _TERMINAL_STATES:
                return
            job.status = status
            job.error = error
            job.updated_at = float(self._clock_fn())
            if status == "completed":
                self._completed_count += 1
            elif status == "failed":
                self._failed_count += 1
            elif status == "canceled":
                self._canceled_count += 1
            self._prune_history_locked()
        self._emit(job, status, error=error or None)

    def _prune_history_locked(self) -> None:
        terminal_ids = [
            job_id
            for job_id in self._job_order
            if job_id in self._jobs and self._jobs[job_id].status in _TERMINAL_STATES
        ]
        remove_count = max(0, len(terminal_ids) - self._max_history)
        for job_id in terminal_ids[:remove_count]:
            self._jobs.pop(job_id, None)
            try:
                self._job_order.remove(job_id)
            except ValueError:
                pass

    def _emit(
        self,
        job: _OutboundTransferJob,
        event: str,
        **details: object,
    ) -> None:
        if not callable(self._progress_fn):
            return
        with self._lock:
            payload = self._job_snapshot_locked(job)
        payload["event"] = event
        payload.update(details)
        try:
            self._progress_fn(payload)
        except Exception:
            return

    def _job_snapshot_locked(self, job: _OutboundTransferJob) -> dict[str, object]:
        return {
            "job_id": job.job_id,
            "transfer_id": job.transfer_id,
            "destination_id": job.destination_id,
            "channel_index": job.channel_index,
            "file_name": job.file_name,
            "file_size": job.file_size,
            "total_chunks": job.total_chunks,
            "status": job.status,
            "error": job.error or None,
            "sent_frames": job.sent_frames,
            "sent_chunks": job.sent_chunks,
            "retry_count": job.retry_count,
            "ack_count": job.ack_count,
            "acked_chunks": job.acked_chunks,
            "cancel_requested": job.cancel_requested,
            "submitted_at": job.submitted_at,
            "updated_at": job.updated_at,
        }


def _canonical_direct_node_id(value: object) -> str:
    clean = str(value or "").strip().lower()
    if _CANONICAL_NODE_ID_RE.fullmatch(clean):
        return clean if clean not in {"!00000000", "!ffffffff"} else ""
    if value is None or isinstance(value, bool):
        return ""
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if 0 < numeric < 0xFFFFFFFF:
        return f"!{numeric:08x}"
    return ""


def _channel_index(value: object) -> int | None:
    if value is None:
        return 0
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if 0 <= parsed <= 7 else None


def _positive_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _parse_frame(frame: object, *, max_file_bytes: int) -> dict[str, object] | None:
    if isinstance(frame, Mapping):
        try:
            text = file_transfer_frame_text(frame)
        except Exception:
            return None
    else:
        text = str(frame or "")
    if not text:
        return None
    return parse_file_transfer_frame_text(text, max_file_bytes=max_file_bytes)


def _bitmap_indexes(bitmap: object, *, total_chunks: int) -> set[int]:
    if not isinstance(bitmap, (bytes, bytearray, memoryview)):
        return set()
    raw = bytes(bitmap)
    return {
        index
        for index in range(max(0, int(total_chunks)))
        if index // 8 < len(raw) and raw[index // 8] & (1 << (index % 8))
    }


def build_outbound_file_transfer_service(**kwargs: object) -> OutboundFileTransferService:
    return OutboundFileTransferService(**kwargs)  # type: ignore[arg-type]


__all__ = [
    "ApprovedPathFileResolver",
    "OutboundFileResolver",
    "OutboundFileTransferService",
    "ResolvedOutboundFile",
    "build_outbound_file_transfer_service",
]
