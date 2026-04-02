import threading
import time
from typing import Callable, Optional

from .helpers import to_int as _to_int

_DEFAULT_MAX_FAULT_ROWS = 2048


def _safe_strftime(unix_seconds: object) -> str:
    value = _to_int(unix_seconds)
    if value is None or value <= 0:
        return "n/a"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))
    except Exception:
        return "n/a"


class FaultRecorder:
    def __init__(
        self,
        *,
        max_rows: int = _DEFAULT_MAX_FAULT_ROWS,
        now_unix_fn: Callable[[], float] = time.time,
    ) -> None:
        self._max_rows = max(1, int(max_rows))
        self._now_unix_fn = now_unix_fn
        self._rows: list[dict[str, object]] = []
        self._seq = 0
        self._lock = threading.Lock()

    def record_fault(self, entry: dict[str, object]) -> dict[str, object]:
        now_unix = int(self._now_unix_fn())
        with self._lock:
            self._seq += 1
            seq = self._seq
            row = dict(entry if isinstance(entry, dict) else {})
            row.setdefault("created_unix", now_unix)
            row.setdefault("created_at", _safe_strftime(now_unix))
            row.setdefault("source", str(row.get("source") or "system").strip().lower() or "system")
            row.setdefault("severity", str(row.get("severity") or "error").strip().lower() or "error")
            row.setdefault("code", str(row.get("code") or "UNKNOWN").strip().upper() or "UNKNOWN")
            row.setdefault("message", str(row.get("message") or "").strip())
            row.setdefault("id", f"fault-{now_unix}-{seq}")
            row["_seq"] = seq
            self._rows.append(row)
            if len(self._rows) > self._max_rows:
                self._rows = self._rows[-self._max_rows :]
        return {k: v for k, v in row.items() if not str(k).startswith("_")}

    def recent_faults(
        self,
        limit: int = 200,
        *,
        source: Optional[str] = None,
    ) -> list[dict[str, object]]:
        max_rows = max(1, min(2000, int(limit)))
        source_filter = str(source or "").strip().lower()
        with self._lock:
            rows = list(self._rows)
        rows.sort(
            key=lambda row: (
                _to_int(row.get("created_unix")) or 0,
                _to_int(row.get("_seq")) or 0,
            ),
            reverse=True,
        )
        out: list[dict[str, object]] = []
        for row in rows:
            if source_filter:
                row_source = str(row.get("source") or "").strip().lower()
                if row_source != source_filter:
                    continue
            clean = {k: v for k, v in row.items() if not str(k).startswith("_")}
            out.append(clean)
            if len(out) >= max_rows:
                break
        return out


__all__ = [
    "FaultRecorder",
]
