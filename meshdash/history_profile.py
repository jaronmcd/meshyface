import os
import re
import time

_CANONICAL_NODE_ID_RE = re.compile(r"^![0-9a-fA-F]{8}$")
_PROFILE_KEY_MAX_LEN = 64


def _slugify(text: object) -> str:
    parts = re.findall(r"[a-z0-9]+", str(text or "").strip().lower())
    if not parts:
        return ""
    return "-".join(parts)[:_PROFILE_KEY_MAX_LEN]


def _key_from_local_node_id(local_node_id: object) -> str:
    raw = str(local_node_id or "").strip()
    if not raw:
        return ""
    if _CANONICAL_NODE_ID_RE.fullmatch(raw):
        return raw[1:].lower()
    lowered = raw.lower()
    if lowered in {"local", "^all", "broadcast"}:
        return ""
    return _slugify(lowered)


def resolve_history_profile_key(
    *,
    iface: object,
    get_local_node_id_fn: object,
    mesh_target_label: str,
    wait_for_id_seconds: float = 0.0,
    poll_interval_seconds: float = 0.2,
    now_unix_fn=time.time,
    sleep_fn=time.sleep,
) -> str:
    if callable(get_local_node_id_fn):
        local_node_id = ""
        wait_seconds = max(0.0, float(wait_for_id_seconds or 0.0))
        poll_seconds = max(0.05, float(poll_interval_seconds or 0.0))
        deadline = now_unix_fn() + wait_seconds

        while True:
            try:
                local_node_id = str(get_local_node_id_fn(iface) or "").strip()
            except Exception:
                local_node_id = ""

            local_key = _key_from_local_node_id(local_node_id)
            if local_key:
                return local_key
            if wait_seconds <= 0.0:
                break
            now = now_unix_fn()
            if now >= deadline:
                break
            sleep_fn(min(poll_seconds, max(0.0, deadline - now)))

    target_key = _slugify(mesh_target_label)
    if target_key:
        return target_key
    return "unknown"


def _is_memory_or_uri_path(db_path: str) -> bool:
    lowered = db_path.strip().lower()
    if lowered in {":memory:", "file::memory:"}:
        return True
    if lowered.startswith("file:"):
        return True
    if "mode=memory" in lowered:
        return True
    return False


def build_profiled_history_db_path(history_db_path: str, *, profile_key: str) -> str:
    raw_path = str(history_db_path or "").strip()
    if not raw_path or _is_memory_or_uri_path(raw_path):
        return raw_path

    key = _slugify(profile_key) or "unknown"
    root, ext = os.path.splitext(raw_path)
    suffix = f".radio-{key}"
    if root.endswith(suffix):
        return raw_path
    return f"{root}{suffix}{ext}"


def local_node_id_from_profiled_history_db_path(history_db_path: str) -> str:
    """Best-effort local node id extraction from a profiled DB path.

    Paths are typically formatted as:
      <base>.radio-<profile-key>.sqlite3

    When <profile-key> is an 8-hex canonical node id slug, return "!<hex>".
    Otherwise return "" (non-node profile keys such as target slugs).
    """
    raw_path = str(history_db_path or "").strip()
    if not raw_path or _is_memory_or_uri_path(raw_path):
        return ""

    base_name = os.path.basename(raw_path)
    root, _ext = os.path.splitext(base_name)
    marker = ".radio-"
    if marker not in root:
        return ""
    profile_key = root.rsplit(marker, 1)[-1].strip()
    if not profile_key:
        return ""
    if re.fullmatch(r"[0-9a-fA-F]{8}", profile_key):
        return f"!{profile_key.lower()}"
    return ""
