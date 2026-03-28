import hashlib
import secrets
import threading
import time

from .games.zork import ZorkGame

_STANDALONE_ZORK_LOCAL_NODE_ID = "!70f70001"
_STANDALONE_ZORK_SESSION_PEER_HEX_CHARS = 16
_DEFAULT_MAX_STANDALONE_ZORK_SESSIONS = 256


def _normalize_session_id(value: object) -> str:
    text = str(value or "").strip()
    return text[:128]


def _session_peer_id(session_id: str) -> str:
    digest = hashlib.sha1(str(session_id).encode("utf-8")).hexdigest()
    return f"!{digest[:_STANDALONE_ZORK_SESSION_PEER_HEX_CHARS]}"


class StandaloneZorkService:
    def __init__(self, *, now_unix_fn=time.time, max_sessions: int = _DEFAULT_MAX_STANDALONE_ZORK_SESSIONS) -> None:
        self._game = ZorkGame()
        self._lock = threading.Lock()
        self._now_unix_fn = now_unix_fn
        self._max_sessions = max(1, int(max_sessions))

    def play(self, *, text: object, session_id: object = None) -> dict[str, object]:
        clean_text = str(text or "").strip()
        clean_session_id = _normalize_session_id(session_id) or secrets.token_hex(16)
        if not clean_text:
            return {"ok": False, "error": "Enter a command.", "session_id": clean_session_id}
        peer_id = _session_peer_id(clean_session_id)
        now_unix = int(self._now_unix_fn())
        with self._lock:
            self._game.prune_expired_sessions(now_unix)
            active_before = self._game.has_active_session(peer_id)
            if not active_before and clean_text.lower() == "zork" and self._game.active_session_count() >= self._max_sessions:
                return {
                    "ok": False,
                    "error": "Standalone Zork is at capacity. Try again shortly.",
                    "session_id": clean_session_id,
                    "active_session": False,
                }
            if not active_before and clean_text.lower() != "zork":
                return {
                    "ok": False,
                    "error": "No active standalone Zork session. Send 'zork' to start.",
                    "session_id": clean_session_id,
                    "active_session": False,
                }
            result = self._game.try_handle_message(
                text=clean_text,
                from_id=peer_id,
                to_id=_STANDALONE_ZORK_LOCAL_NODE_ID,
                local_node_id=_STANDALONE_ZORK_LOCAL_NODE_ID,
                now_unix=now_unix,
                enabled=True,
            )
            active_after = self._game.has_active_session(peer_id)
        if not getattr(result, "handled", False):
            return {
                "ok": False,
                "error": "Command was not handled.",
                "session_id": clean_session_id,
                "active_session": active_after,
            }
        return {
            "ok": True,
            "session_id": clean_session_id,
            "reply_text": str(getattr(result, "reply_text", "") or "").strip(),
            "command_name": str(getattr(result, "command_name", "") or "").strip(),
            "active_session": bool(active_after),
        }


def build_standalone_zork_service() -> StandaloneZorkService:
    return StandaloneZorkService()


__all__ = [
    "StandaloneZorkService",
    "build_standalone_zork_service",
]
