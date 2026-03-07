from typing import Optional

from .world import ROOMS, START_ROOM

GAME_SESSION_TTL_SECONDS = 45 * 60

GAME_VERB_HEADS = {
    "zork",
    "!zork",
    "#zork",
    "help",
    "look",
    "l",
    "inventory",
    "inv",
    "i",
    "north",
    "n",
    "south",
    "s",
    "east",
    "e",
    "west",
    "w",
    "take",
    "get",
    "open",
    "quit",
    "exit",
    "restart",
}


class ZorkGame:
    """Simple peer-to-peer text adventure.

    Keep the transport and bot settings in `bot_responder.py`; keep the
    adventure world and rules here so users can rewrite them in one place.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, object]] = {}

    def active_session_count(self) -> int:
        return len(self._sessions)

    def clear_sessions(self) -> None:
        self._sessions.clear()

    def _room_summary(self, room_id: str, session: dict[str, object]) -> str:
        room = ROOMS.get(room_id) or ROOMS[START_ROOM]
        exits_map = room.get("exits") if isinstance(room, dict) else {}
        exits = []
        if isinstance(exits_map, dict):
            for direction, target in exits_map.items():
                if str(target) == "vault" and "gate_unlocked" not in set(session.get("flags") or []):
                    continue
                exits.append(str(direction))
        exits_text = "/".join(exits) if exits else "none"
        item = str(room.get("item") or "").strip().lower()
        inventory = {str(value).strip().lower() for value in (session.get("inventory") or [])}
        item_text = ""
        if item and item not in inventory:
            item_text = f" Item: {item}."
        return f"{room.get('name')}: {room.get('desc')} Exits {exits_text}.{item_text}"

    def _prune_sessions(self, now_unix: int) -> None:
        stale_before = now_unix - GAME_SESSION_TTL_SECONDS
        for peer_id, session in list(self._sessions.items()):
            updated_unix = int(session.get("updated_unix") or 0)
            if updated_unix and updated_unix >= stale_before:
                continue
            self._sessions.pop(peer_id, None)

    def _start_session(self, from_id: str, now_unix: int) -> dict[str, object]:
        peer_id = str(from_id or "").strip().lower()
        session = {
            "peer_id": peer_id,
            "room": START_ROOM,
            "inventory": [],
            "flags": [],
            "moves": 0,
            "started_unix": now_unix,
            "updated_unix": now_unix,
        }
        self._sessions[peer_id] = session
        return session

    def _is_direct_to_local(self, to_id: str, local_node_id: str) -> bool:
        clean_to = str(to_id or "").strip().lower()
        clean_local = str(local_node_id or "").strip().lower()
        if not clean_to.startswith("!"):
            return False
        if not clean_local.startswith("!"):
            return False
        return clean_to == clean_local

    def try_handle_message(
        self,
        *,
        text: str,
        from_id: str,
        to_id: str,
        local_node_id: str,
        now_unix: int,
        enabled: bool,
    ) -> tuple[bool, Optional[str], str]:
        raw = str(text or "").strip()
        if not raw:
            return False, None, ""
        parts = [part for part in raw.split() if part]
        if not parts:
            return False, None, ""
        head_raw = str(parts[0]).strip().lower()
        if head_raw not in GAME_VERB_HEADS:
            return False, None, ""
        if not self._is_direct_to_local(to_id, local_node_id):
            return False, None, ""

        peer_id = str(from_id or "").strip().lower()
        if not peer_id.startswith("!"):
            return False, None, ""

        self._prune_sessions(now_unix)
        session = self._sessions.get(peer_id)
        if head_raw in ("zork", "!zork", "#zork", "restart"):
            if not enabled:
                return True, None, "zork"
            session = self._start_session(from_id, now_unix)
            summary = self._room_summary(str(session.get("room") or START_ROOM), session)
            return True, f"zork: session started. {summary}", "zork"

        if session is None:
            return False, None, ""
        if not enabled:
            return True, None, "zork"

        room_id = str(session.get("room") or START_ROOM)
        inventory = {str(value).strip().lower() for value in (session.get("inventory") or [])}
        flags = {str(value).strip().lower() for value in (session.get("flags") or [])}
        args = [str(value).strip().lower() for value in parts[1:] if str(value).strip()]
        moved = False
        feedback = ""

        if head_raw in ("help",):
            feedback = "zork help: look, n/s/e/w, take <item>, open gate, inventory, quit."
        elif head_raw in ("look", "l"):
            feedback = self._room_summary(room_id, session)
        elif head_raw in ("inventory", "inv", "i"):
            if inventory:
                feedback = f"inventory: {', '.join(sorted(inventory))}"
            else:
                feedback = "inventory: empty"
        elif head_raw in ("quit", "exit"):
            self._sessions.pop(peer_id, None)
            return True, "zork: session ended. Send 'zork' to start again.", "zork"
        elif head_raw in ("open",):
            target = args[0] if args else ""
            if target in ("gate", "door"):
                if room_id != "gate":
                    feedback = "zork: no gate here."
                elif "key" in inventory:
                    flags.add("gate_unlocked")
                    feedback = "zork: gate unlocked. Path north is open."
                else:
                    feedback = "zork: locked. You need a key."
            else:
                feedback = "zork: try 'open gate'."
        elif head_raw in ("take", "get"):
            room = ROOMS.get(room_id) or {}
            item = str(room.get("item") or "").strip().lower()
            wanted = args[0] if args else item
            if not item:
                feedback = "zork: nothing to take."
            elif wanted and wanted != item:
                feedback = f"zork: no {wanted} here."
            elif item in inventory:
                feedback = f"zork: you already have {item}."
            else:
                inventory.add(item)
                if item == "beacon":
                    feedback = "zork: you secured the beacon. Victory."
                else:
                    feedback = f"zork: took {item}."
        elif head_raw in ("north", "n", "south", "s", "east", "e", "west", "w"):
            direction_map = {
                "north": "north",
                "n": "north",
                "south": "south",
                "s": "south",
                "east": "east",
                "e": "east",
                "west": "west",
                "w": "west",
            }
            direction = direction_map.get(head_raw, "")
            room = ROOMS.get(room_id) or {}
            exits = room.get("exits") if isinstance(room, dict) else {}
            target = ""
            if isinstance(exits, dict):
                target = str(exits.get(direction) or "").strip().lower()
            if not target:
                feedback = f"zork: can't go {direction}."
            elif target == "vault" and "gate_unlocked" not in flags:
                feedback = "zork: gate is locked. Try 'open gate'."
            elif target not in ROOMS:
                feedback = f"zork: path {direction} is blocked."
            else:
                room_id = target
                moved = True
        else:
            feedback = "zork: unknown action. Try 'help'."

        session["room"] = room_id
        session["inventory"] = sorted(inventory)
        session["flags"] = sorted(flags)
        session["updated_unix"] = now_unix
        session["moves"] = int(session.get("moves") or 0) + 1
        self._sessions[peer_id] = session

        if moved:
            return True, self._room_summary(room_id, session), "zork"
        if feedback:
            if head_raw in ("look", "l", "help", "inventory", "inv", "i"):
                return True, feedback, "zork"
            return True, f"{feedback} {self._room_summary(room_id, session)}", "zork"
        return True, self._room_summary(room_id, session), "zork"
