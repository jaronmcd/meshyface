from __future__ import annotations

from collections.abc import Iterable
import re

from ...bot_apps.base import BotAppResult
from ...bot_commands import BotCommandSpec

from .world import INITIAL_OBJECT_LOCATIONS, OBJECTS, ROOMS, START_ROOM, object_name, room_name


GAME_SESSION_TTL_SECONDS = 45 * 60
MAX_GAME_SESSIONS = 128
# Set to 0 to disable truncation and let transport-layer chunking handle limits.
MAX_REPLY_CHARS = 0
START_HELP_HINT = "Type 'help' for the command set."

BASELINE_OBJECT_LOCATIONS = {
    code: ("SAFEBOX" if code in {"CROWN", "CARD"} and location == "SAFE" else location)
    for code, location in INITIAL_OBJECT_LOCATIONS.items()
}

DIRECTION_ALIASES = {
    "north": "NORTH",
    "n": "NORTH",
    "south": "SOUTH",
    "s": "SOUTH",
    "east": "EAST",
    "e": "EAST",
    "west": "WEST",
    "w": "WEST",
    "up": "UP",
    "u": "UP",
    "down": "DOWN",
    "d": "DOWN",
    "northeast": "NE",
    "ne": "NE",
    "northwest": "NW",
    "nw": "NW",
    "southeast": "SE",
    "se": "SE",
    "southwest": "SW",
    "sw": "SW",
    "enter": "ENTER",
    "in": "ENTER",
    "exit": "EXIT",
    "out": "OUT",
    "cross": "CROSS",
    "climb": "CLIMB",
    "launch": "LAUNC",
    "launc": "LAUNC",
    "land": "LAND",
}

GAME_VERB_HEADS = {
    "zork",
    "!zork",
    "#zork",
    "help",
    "look",
    "l",
    "examine",
    "x",
    "inventory",
    "inv",
    "i",
    "score",
    "north",
    "n",
    "south",
    "s",
    "east",
    "e",
    "west",
    "w",
    "up",
    "u",
    "down",
    "d",
    "ne",
    "nw",
    "se",
    "sw",
    "enter",
    "in",
    "exit",
    "out",
    "go",
    "walk",
    "take",
    "get",
    "give",
    "drop",
    "read",
    "eat",
    "put",
    "insert",
    "plug",
    "repair",
    "patch",
    "throw",
    "rub",
    "melt",
    "dig",
    "open",
    "close",
    "unlock",
    "move",
    "lift",
    "wave",
    "tie",
    "untie",
    "push",
    "press",
    "tell",
    "raise",
    "lower",
    "robot",
    "pray",
    "exorcise",
    "attack",
    "fight",
    "kill",
    "light",
    "burn",
    "extinguish",
    "inflate",
    "deflate",
    "turn",
    "on",
    "off",
    "cross",
    "climb",
    "launch",
    "land",
    "board",
    "disembark",
    "well",
    "sinbad",
    "geronimo",
    "quit",
    "exitgame",
    "restart",
}

ROOM_DYNAMIC_DESCRIPTIONS = {
    "KITCH": (
        "You are in the kitchen of the white house. A table seems to have been used recently for food. "
        "A passage leads west and a dark staircase leads up. To the east is a small window which is {window_state}."
    ),
    "LROOM": (
        "You are in the living room. There is a door to the east and a wooden door with strange gothic lettering to the west, {center_state}."
    ),
    "CLEAR": (
        "You are in a clearing, with a forest surrounding you on the west and south. {grating_state}"
    ),
    "MTROL": (
        "You are in a small room with passages off in all directions. Bloodstains and deep scratches mar the walls. {troll_state}"
    ),
    "MTORC": (
        "You are in a large room with a prominent doorway leading to a down staircase. To the west is a narrow twisting tunnel. "
        "Above you is a large dome painted with scenes depicting elfin hacking rites. Up around the edge of the dome is a wooden railing. "
        "In the center of the room there is a white marble pedestal. {rope_state}"
    ),
    "DOME": (
        "You are at the periphery of a large dome, which forms the ceiling of another room below. Protecting you from a precipitous drop "
        "is a wooden railing which circles the dome. {rope_state}"
    ),
    "FALLS": (
        "You are at the top of Aragain Falls, an enormous waterfall with a drop of about 450 feet. The only path here is on the north end. "
        "There is a man-sized barrel here which you could fit into. {rainbow_state}"
    ),
    "CYCLO": (
        "You are in a room with an exit on the west side, and a staircase leading up. {cyclops_state} {north_state}"
    ),
    "ICY": "You are in a large room, with giant icicles hanging from the walls and ceiling. {west_state}",
    "MIRR1": (
        "You are in a large square room with tall ceilings. On the south wall is an enormous mirror which fills the entire wall. "
        "There are exits on the other three sides of the room. {mirror_state}"
    ),
    "MIRR2": (
        "You are in a large square room with tall ceilings. On the south wall is an enormous mirror which fills the entire wall. "
        "There are exits on the other three sides of the room. {mirror_state}"
    ),
    "MACHI": "You are in a cramped machine room at the east end of the shaft. A heavy machine dominates the chamber, {machine_state}",
    "SAFE": (
        "You are in a dusty old room which is virtually featureless, except for an exit on the north side. {safe_state}"
    ),
    "LEDG2": (
        "You are on a narrow ledge overlooking the inside of an old dormant volcano. This ledge appears to be about in the middle between the floor below and the rim above. There is an exit here to the south. {west_state}"
    ),
    "LEDG4": (
        "You are on a wide ledge high into the volcano. The rim of the volcano is about 200 feet above and there is a precipitous drop below to the bottom. {south_state} {west_state}"
    ),
    "CAROU": "You are in a circular room with passages off in eight directions. {bearing_state}",
    "CMACH": (
        "You are in a large room full of assorted heavy machinery. The room smells of burned resistors and the whirring of machinery fills the air. "
        "Along one wall are three buttons: round, triangular, and square. A large sign above them says 'DANGER -- HIGH VOLTAGE'."
    ),
    "MAGNE": "You are in a room with a low circular ceiling. There are exits to the east and the southeast.",
    "ALITR": "You are in a large room, one half of which is depressed. {pool_state} The only exit to this room is to the west.",
    "LLD2": (
        "You have entered the Land of the Living Dead, a large desolate room. Although it is apparently uninhabited, "
        "you can hear the sounds of thousands of lost souls weeping and moaning. In the east corner are stacked the remains "
        "of dozens of previous adventurers who were less fortunate than yourself. To the east is an ornate passage, apparently recently constructed."
    ),
}

NATURALLY_LIT_ROOMS = {
    "RESES",
    "RESEN",
    "RIVR1",
    "RIVR2",
    "RIVR3",
    "RIVR4",
    "RIVR5",
    "WCLF1",
    "WCLF2",
    "FANTE",
    "BEACH",
    "RCAVE",
    "FALLS",
    "BARRE",
    "VLBOT",
    "VAIR1",
    "VAIR2",
    "VAIR3",
    "VAIR4",
    "LEDG2",
    "LEDG4",
}

TREASURE_CODES = frozenset(
    {
        "BAGCO",
        "BAR",
        "BRACE",
        "CHALI",
        "COFFI",
        "CROWN",
        "DIAMO",
        "EMERA",
        "GRAIL",
        "JADE",
        "PAINT",
        "PEARL",
        "POT",
        "RUBY",
        "STATU",
        "STRAD",
        "TRIDE",
        "TRUNK",
        "ZORKM",
    }
)

INLINE_CONTAINER_SUMMARY_CODES = frozenset({"TCASE"})
BULK_SCOPE_ALL_WORDS = frozenset({"all", "everything"})
BULK_SCOPE_TREASURE_WORDS = frozenset({"treasure", "treasures", "valuable", "valuables"})
BAT_DROP_ROOMS = ("MINE1", "MINE2", "MINE3", "MINE4", "MINE5", "MINE6", "MINE7", "TLADD", "BLADD")
GNOME_LEDGE_ROOMS = frozenset({"LEDG2", "LEDG4"})
WEAPON_CODES = frozenset({"SWORD", "KNIFE", "RKNIF", "AXE", "STILL"})

THIEF_FORBIDDEN_ROOMS = frozenset(
    {
        "ATTIC",
        "BEACH",
        "CLEAR",
        "DAM",
        "DOCK",
        "EHOUS",
        "FALLS",
        "FANTE",
        "FORE1",
        "FORE2",
        "FORE3",
        "FORE4",
        "FORE5",
        "KITCH",
        "LEDG2",
        "LEDG3",
        "LEDG4",
        "LLD1",
        "LLD2",
        "LOBBY",
        "LROOM",
        "MAINT",
        "NHOUS",
        "POG",
        "RAINB",
        "RCAVE",
        "RESEN",
        "RESES",
        "RIVR1",
        "RIVR2",
        "RIVR3",
        "RIVR4",
        "RIVR5",
        "SHOUS",
        "STREA",
        "STUDI",
        "TEMP1",
        "TEMP2",
        "TOMB",
        "VAIR1",
        "VAIR2",
        "VAIR3",
        "VAIR4",
        "VLBOT",
        "WCLF1",
        "WCLF2",
        "WHOUS",
    }
)
THIEF_HOME_ROOM = "TREAS"

BALLOON_LAUNCH_MAP = {
    "VLBOT": "VAIR1",
    "LEDG2": "VAIR2",
    "LEDG4": "VAIR4",
}
BALLOON_ASCENT_MAP = {
    "VAIR1": "VAIR2",
    "VAIR2": "VAIR3",
    "VAIR3": "VAIR4",
}
BALLOON_DESCENT_MAP = {
    "VAIR1": "VLBOT",
    "VAIR2": "VAIR1",
    "VAIR3": "VAIR2",
    "VAIR4": "VAIR3",
}
BALLOON_LANDING_MAP = {
    "VAIR1": "VLBOT",
    "VAIR2": "LEDG2",
    "VAIR4": "LEDG4",
}
BALLOON_HOOK_CODES = {
    "LEDG2": "HOOK1",
    "LEDG4": "HOOK2",
}
BALLOON_AIR_ROOMS = frozenset({"VAIR1", "VAIR2", "VAIR3", "VAIR4"})
BALLOON_GROUND_ROOMS = frozenset({"VLBOT", "LEDG2", "LEDG4"})
BALLOON_FUEL_TURNS = {
    "COAL": 6,
    "BOOK": 4,
    "GUIDE": 4,
    "LISTS": 4,
    "LEAVE": 3,
    "PAPER": 2,
    "ADVER": 2,
    "BLABE": 2,
    "CARD": 2,
    "STAMP": 2,
    "RBTLB": 2,
}
DEFAULT_BALLOON_FUEL_TURNS = 3

CAROUSEL_RANDOM_TARGETS = (
    "CAVE4",
    "CAVE4",
    "MGRAI",
    "PASS1",
    "CANY1",
    "PASS5",
    "PASS4",
    "MAZE1",
)
MAGNET_FIXED_TARGETS = {
    "NORTH": "CMACH",
    "SOUTH": "CMACH",
    "WEST": "CMACH",
    "NE": "CMACH",
    "EAST": "CMACH",
    "NW": "ALICE",
    "SW": "ALICE",
    "SE": "ALICE",
}
MAGNET_RANDOM_TARGETS = tuple(MAGNET_FIXED_TARGETS[direction] for direction in ("NORTH", "SOUTH", "WEST", "NE", "NW", "SW", "SE", "EAST"))


class ZorkGame:
    """Peer-to-peer classic Zork gameplay.

    The transport shell remains generic, but the Zork game logic lives here.
    This implementation keeps the game isolated to the `meshdash/games/zork/`
    folder and drives the live bot from the archived upstream map + object data.
    """

    SPEC = BotCommandSpec(
        name="zork",
        usage="zork",
        description="start a peer-to-peer Zork session",
        kind="game",
    )

    def __init__(self, *, max_sessions: int = MAX_GAME_SESSIONS) -> None:
        self._sessions: dict[str, dict[str, object]] = {}
        self._max_sessions = max(1, int(max_sessions))

    def active_session_count(self) -> int:
        return len(self._sessions)

    def clear_sessions(self) -> None:
        self._sessions.clear()

    def end_session(self, from_id: str) -> bool:
        peer_id = str(from_id or "").strip().lower()
        if not peer_id:
            return False
        return self._sessions.pop(peer_id, None) is not None

    def session_summaries(self, now_unix: int | None = None) -> list[dict[str, object]]:
        if now_unix is not None:
            self._prune_sessions(int(now_unix))
        sessions: list[dict[str, object]] = []
        for peer_id, session in sorted(
            self._sessions.items(),
            key=lambda item: int(item[1].get("updated_unix") or 0),
            reverse=True,
        ):
            room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
            inventory = self._session_inventory(session)
            seen_rooms = {
                str(value).strip().upper()
                for value in (session.get("seen_rooms") or [])
                if str(value).strip()
            }
            total_treasures, recovered, carried, secured = self._treasure_progress(session)
            updated_unix = int(session.get("updated_unix") or 0)
            summary = {
                "peer_id": peer_id,
                "room": room_id,
                "room_name": room_name(room_id),
                "moves": int(session.get("moves") or 0),
                "started_unix": int(session.get("started_unix") or 0),
                "updated_unix": updated_unix,
                "expires_unix": updated_unix + GAME_SESSION_TTL_SECONDS if updated_unix else 0,
                "inventory_count": len(inventory),
                "seen_room_count": len(seen_rooms),
                "treasures": {
                    "total": total_treasures,
                    "recovered": recovered,
                    "carried": carried,
                    "secured": secured,
                },
            }
            sessions.append(summary)
        return sessions

    def prune_expired_sessions(self, now_unix: int) -> None:
        self._prune_sessions(int(now_unix))

    def has_active_session(self, from_id: str) -> bool:
        peer_id = str(from_id or "").strip().lower()
        if not peer_id:
            return False
        return peer_id in self._sessions

    def _is_direct_to_local(self, to_id: str, local_node_id: str) -> bool:
        clean_to = str(to_id or "").strip().lower()
        clean_local = str(local_node_id or "").strip().lower()
        if not clean_to.startswith("!"):
            return False
        if not clean_local.startswith("!"):
            return False
        return clean_to == clean_local

    def _prune_sessions(self, now_unix: int) -> None:
        stale_before = now_unix - GAME_SESSION_TTL_SECONDS
        for peer_id, session in list(self._sessions.items()):
            updated_unix = int(session.get("updated_unix") or 0)
            if updated_unix and updated_unix >= stale_before:
                continue
            self._sessions.pop(peer_id, None)

    def _start_session(self, from_id: str, now_unix: int) -> dict[str, object]:
        peer_id = str(from_id or "").strip().lower()
        self._prune_sessions(now_unix)
        if peer_id not in self._sessions and len(self._sessions) >= self._max_sessions:
            oldest_peer_id = min(
                self._sessions,
                key=lambda candidate: int(
                    self._sessions[candidate].get("updated_unix") or 0
                ),
            )
            self._sessions.pop(oldest_peer_id, None)
        object_locations = dict(INITIAL_OBJECT_LOCATIONS)
        for hidden_code in ("CROWN", "CARD"):
            if object_locations.get(hidden_code) == "SAFE":
                object_locations[hidden_code] = "SAFEBOX"
        session = {
            "peer_id": peer_id,
            "room": START_ROOM,
            "inventory": [],
            "flags": [],
            "moves": 0,
            "seen_rooms": [],
            "object_locations": object_locations,
            "started_unix": now_unix,
            "updated_unix": now_unix,
        }
        self._sessions[peer_id] = session
        return session

    def _session_flags(self, session: dict[str, object]) -> set[str]:
        return {str(value).strip().lower() for value in (session.get("flags") or []) if str(value).strip()}

    def _session_inventory(self, session: dict[str, object]) -> list[str]:
        return [str(value).strip().upper() for value in (session.get("inventory") or []) if str(value).strip()]

    def _object_locations(self, session: dict[str, object]) -> dict[str, str]:
        raw_locations = session.get("object_locations")
        if isinstance(raw_locations, dict):
            return {str(key).strip().upper(): str(value).strip().upper() for key, value in raw_locations.items() if str(key).strip() and str(value).strip()}
        return dict(INITIAL_OBJECT_LOCATIONS)

    def _container_location_code(self, code: str) -> str:
        code_key = str(code or "").strip().upper()
        if code_key == "MACHI":
            return "MACHINE"
        if code_key == "SAFE":
            return "SAFEBOX"
        return code_key

    def _location_container_code(self, location: str) -> str:
        location_key = str(location or "").strip().upper()
        if location_key == "MACHINE":
            return "MACHI"
        if location_key == "SAFEBOX":
            return "SAFE"
        return location_key

    def _write_session_state(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: Iterable[str],
        flags: Iterable[str],
        object_locations: dict[str, str],
        now_unix: int,
    ) -> None:
        seen_rooms = {str(value).strip().upper() for value in (session.get("seen_rooms") or []) if str(value).strip()}
        seen_rooms.add(str(room_id or START_ROOM).strip().upper())
        session["room"] = str(room_id or START_ROOM).strip().upper() or START_ROOM
        session["inventory"] = sorted({str(value).strip().upper() for value in inventory if str(value).strip()})
        session["flags"] = sorted({str(value).strip().lower() for value in flags if str(value).strip()})
        session["object_locations"] = dict(sorted((str(key).strip().upper(), str(value).strip().upper()) for key, value in object_locations.items() if str(key).strip() and str(value).strip()))
        session["updated_unix"] = now_unix
        session["moves"] = int(session.get("moves") or 0) + 1
        session["seen_rooms"] = sorted(seen_rooms)

    def _ephemeral_session(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: Iterable[str],
        flags: Iterable[str],
        object_locations: dict[str, str],
    ) -> dict[str, object]:
        ghost = dict(session)
        ghost["room"] = str(room_id or START_ROOM).strip().upper() or START_ROOM
        ghost["inventory"] = sorted({str(value).strip().upper() for value in inventory if str(value).strip()})
        ghost["flags"] = sorted({str(value).strip().lower() for value in flags if str(value).strip()})
        ghost["object_locations"] = dict(object_locations)
        return ghost

    def _room_summary_for_state(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: Iterable[str],
        flags: Iterable[str],
        object_locations: dict[str, str],
        explicit_look: bool = False,
    ) -> str:
        ghost = self._ephemeral_session(
            session,
            room_id=room_id,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
        )
        return self._room_summary(ghost, room_id, explicit_look=explicit_look)

    def _mark_room_seen(self, session: dict[str, object], room_id: str) -> None:
        seen_rooms = {str(value).strip().upper() for value in (session.get("seen_rooms") or []) if str(value).strip()}
        seen_rooms.add(str(room_id or START_ROOM).strip().upper())
        session["seen_rooms"] = sorted(seen_rooms)

    def _seen_room(self, session: dict[str, object], room_id: str) -> bool:
        room_key = str(room_id or START_ROOM).strip().upper()
        return room_key in {str(value).strip().upper() for value in (session.get("seen_rooms") or []) if str(value).strip()}

    def _clean_words(self, raw: str) -> list[str]:
        return [part for part in re.findall(r"[a-z0-9]+", str(raw or "").lower()) if part]

    def _extract_robot_command(self, raw: str) -> str | None:
        text = str(raw or "").strip()
        lower = text.lower()
        prefixes = (
            "tell robot to ",
            "tell robot ",
            "robot, ",
            "robot,",
            "robot ",
        )
        for prefix in prefixes:
            if lower.startswith(prefix):
                return text[len(prefix):].strip()
        if lower in {"robot", "tell robot", "tell robot to"}:
            return ""
        return None

    def _bulk_scope(self, raw_target: str) -> str | None:
        words = set(self._clean_words(raw_target))
        if not words:
            return None
        if words & BULK_SCOPE_ALL_WORDS:
            return "all"
        if words & BULK_SCOPE_TREASURE_WORDS:
            return "treasures"
        return None

    def _word_matches_vocab(self, query_word: str, vocabulary: set[str]) -> bool:
        word = str(query_word or "").strip().lower()
        if not word:
            return False
        if word in vocabulary:
            return True
        if len(word) < 4:
            return False
        return any(word.startswith(token) or token.startswith(word) for token in vocabulary if token)

    def _query_matches_vocabulary(self, query_words: Iterable[str], vocabulary: Iterable[str]) -> bool:
        vocab = {str(token).strip().lower() for token in vocabulary if str(token).strip()}
        return all(self._word_matches_vocab(word, vocab) for word in query_words if str(word).strip())

    def _compact(self, text: str, *, limit: int = MAX_REPLY_CHARS) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip())
        if int(limit) <= 0:
            return cleaned
        if len(cleaned) <= limit:
            return cleaned
        clipped = cleaned[: max(0, limit - 1)].rstrip(" ,;:-")
        if not clipped:
            return cleaned[:limit]
        return clipped + "…"

    def _room_object_visible(self, code: str, room_id: str, flags: set[str], object_locations: dict[str, str]) -> bool:
        room_key = str(room_id or START_ROOM).strip().upper()
        code_key = str(code or "").strip().upper()
        if not code_key:
            return False
        if code_key == "STATU" and room_key == "BEACH" and "beach_statue_found" not in flags:
            return False
        if code_key == "POOL" and room_key == "ALITR" and "pool_evaporated" in flags:
            return False
        if code_key == "SAFFR" and room_key == "ALITR" and "pool_evaporated" not in flags:
            return False
        if code_key == "TRUNK" and room_key in {"RESES", "RESEN"} and "low_tide" not in flags:
            return False
        if code_key == "CAGE" and "cage_solved" not in flags:
            return False
        if code_key == "CYCLO" and "cyclops_gone" in flags:
            return False
        if code_key == "RAINB" and room_key in {"FALLS", "POG"}:
            return True
        location = str(object_locations.get(code_key) or room_key).strip().upper()
        if location != room_key:
            return False
        if code_key == "DOOR" and room_key == "LROOM" and "rug_moved" not in flags and "trap_door_open" not in flags:
            return False
        if code_key == "GRAT1" and room_key == "CLEAR" and "leaves_moved" not in flags and "grating_open" not in flags and "grating_unlocked" not in flags:
            return False
        if code_key == "AXE" and object_locations.get("AXE") == "TROLL" and "troll_defeated" not in flags:
            return False
        return True

    def _visible_top_level_objects(self, session: dict[str, object], room_id: str) -> list[str]:
        room = ROOMS.get(str(room_id or START_ROOM).strip().upper())
        if room is None:
            return []
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        visible: list[str] = []
        seen: set[str] = set()
        # Static room graph objects.
        for code in room.visible_object_codes:
            if code in seen:
                continue
            if not self._room_object_visible(code, room_id, flags, object_locations):
                continue
            seen.add(code)
            visible.append(code)
        # Loose/dropped objects in the room.
        for code, location in sorted(object_locations.items()):
            if location != room.code:
                continue
            if code in seen:
                continue
            if code in {"ADVER", "GARLI", "FOOD", "WATER"}:
                continue
            if not self._room_object_visible(code, room_id, flags, object_locations):
                continue
            seen.add(code)
            visible.append(code)
        # Visible contents of opened containers that are represented by non-room location sentinels.
        visible_container_codes = set(visible)
        for code, location in sorted(object_locations.items()):
            container_code = self._location_container_code(location)
            if container_code == location:
                continue
            if container_code not in visible_container_codes:
                continue
            if container_code in INLINE_CONTAINER_SUMMARY_CODES:
                continue
            if not self._container_open(container_code, flags):
                continue
            if code in seen:
                continue
            seen.add(code)
            visible.append(code)
        # Accessible mailbox leaflet as a visible room item when opened.
        if room.code == "WHOUS" and "mailbox_open" in flags and object_locations.get("ADVER") == "MAILB":
            visible.append("ADVER")
        return visible

    def _container_open(self, code: str, flags: set[str]) -> bool:
        code_key = str(code or "").strip().upper()
        if code_key == "MAILB":
            return "mailbox_open" in flags
        if code_key == "BUOY":
            return "buoy_open" in flags
        if code_key == "THIEF":
            return "thief_defeated" in flags
        if code_key in {"MACHI", "MACHINE"}:
            return "machine_open" in flags
        if code_key in {"SAFE", "SAFEBOX"}:
            return "safe_blown" in flags
        if code_key == "RBOAT":
            return True
        if code_key in {"SBAG", "BOTTL", "TCASE"}:
            return True
        if code_key == "TROLL":
            return "troll_defeated" in flags
        return True

    def _container_contents(self, session: dict[str, object], container_code: str) -> list[str]:
        location_key = self._container_location_code(container_code)
        contents = [code for code, location in self._object_locations(session).items() if location == location_key and code in OBJECTS]
        return sorted(contents, key=object_name)

    def _treasure_codes_present(self) -> list[str]:
        return sorted(code for code in TREASURE_CODES if code in OBJECTS)

    def _is_treasure(self, code: str) -> bool:
        return str(code or "").strip().upper() in TREASURE_CODES and str(code or "").strip().upper() in OBJECTS

    def _treasure_progress(self, session: dict[str, object]) -> tuple[int, int, int, int]:
        inventory = set(self._session_inventory(session))
        object_locations = self._object_locations(session)
        treasure_codes = self._treasure_codes_present()
        carried = sum(1 for code in treasure_codes if code in inventory or object_locations.get(code) == "INVENTORY")
        secured = sum(1 for code in treasure_codes if object_locations.get(code) == "TCASE")
        recovered = 0
        for code in treasure_codes:
            baseline = str(BASELINE_OBJECT_LOCATIONS.get(code) or "").strip().upper()
            current = str(object_locations.get(code) or "").strip().upper()
            if code in inventory:
                recovered += 1
                continue
            if current == "THIEF":
                continue
            if current and current != baseline:
                recovered += 1
        return len(treasure_codes), recovered, carried, secured

    def _score_text(self, session: dict[str, object]) -> str:
        seen_rooms = {str(value).strip().upper() for value in (session.get("seen_rooms") or []) if str(value).strip()}
        exploration = sum(ROOMS[code].score_value for code in seen_rooms if code in ROOMS)
        total_treasures, recovered, carried, secured = self._treasure_progress(session)
        misplaced = max(0, recovered - carried - secured)
        parts = [
            f"score/progress: exploration {exploration}",
            f"treasures secured {secured}/{total_treasures}",
            f"treasures carried {carried}",
            f"treasures recovered {recovered}/{total_treasures}",
        ]
        if misplaced:
            parts.append(f"treasures stashed elsewhere {misplaced}")
        return self._compact(". ".join(parts) + ".")

    def _bulk_take_candidates(self, session: dict[str, object], *, treasure_only: bool) -> list[str]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = set(self._session_inventory(session))
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        candidates: list[str] = []
        visible_top_level = self._visible_top_level_objects(session, room_id)
        for code in visible_top_level:
            if code in inventory:
                continue
            if code in {"EVERY", "VALUA", "MAILB", "TCASE"}:
                continue
            item = OBJECTS.get(code)
            if item is None:
                continue
            if treasure_only and not self._is_treasure(code):
                continue
            if "TAKEBIT" not in item.flags and code not in {"AXE", "LEAVE"}:
                continue
            candidates.append(code)
        visible_container_codes = {code for code in visible_top_level if code in OBJECTS}
        for code, location in object_locations.items():
            container_code = self._location_container_code(location)
            if str(location or "").strip().upper() == room_id:
                continue
            if container_code not in visible_container_codes:
                continue
            if not self._container_open(container_code, flags):
                continue
            if code in inventory:
                continue
            item = OBJECTS.get(code)
            if item is None:
                continue
            if treasure_only and not self._is_treasure(code):
                continue
            if "TAKEBIT" not in item.flags and code not in {"AXE", "LEAVE"}:
                continue
            candidates.append(code)
        return sorted(dict.fromkeys(candidates), key=object_name)

    def _bulk_inventory_candidates(self, session: dict[str, object], *, treasure_only: bool) -> list[str]:
        inventory = []
        for code in self._session_inventory(session):
            if treasure_only and not self._is_treasure(code):
                continue
            inventory.append(code)
        return sorted(dict.fromkeys(inventory), key=object_name)

    def _session_counters(self, session: dict[str, object]) -> dict[str, int]:
        raw = session.get("counters")
        if not isinstance(raw, dict):
            raw = {}
            session["counters"] = raw
        cleaned: dict[str, int] = {}
        changed = False
        for key, value in raw.items():
            key_text = str(key or "").strip().lower()
            if not key_text:
                changed = True
                continue
            try:
                cleaned[key_text] = int(value)
            except (TypeError, ValueError):
                cleaned[key_text] = 0
                changed = True
        if changed or cleaned is not raw:
            session["counters"] = cleaned
        return cleaned

    def _villain_locations(self, session: dict[str, object]) -> dict[str, str]:
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        active: dict[str, str] = {}
        if "troll_defeated" not in flags:
            troll_room = str(object_locations.get("TROLL") or "MTROL").strip().upper()
            if troll_room in ROOMS:
                active["TROLL"] = troll_room
        if "cyclops_gone" not in flags:
            cyclops_room = str(object_locations.get("CYCLO") or "CYCLO").strip().upper()
            if cyclops_room in ROOMS:
                active["CYCLO"] = cyclops_room
        if "thief_defeated" not in flags:
            thief_room = str(object_locations.get("THIEF") or "").strip().upper()
            if thief_room in ROOMS:
                active["THIEF"] = thief_room
        return active

    def _sword_glow_level(self, session: dict[str, object], room_id: str | None = None) -> int:
        inventory = set(self._session_inventory(session))
        if "SWORD" not in inventory:
            return 0
        room_key = str(room_id or session.get("room") or START_ROOM).strip().upper() or START_ROOM
        villain_rooms = set(self._villain_locations(session).values())
        if room_key in villain_rooms:
            return 2
        room = ROOMS.get(room_key)
        if room is None:
            return 0
        for exit_row in room.exits:
            target = str(exit_row.get("target") or "").strip().upper()
            if target and target in villain_rooms:
                return 1
        return 0

    def _sword_glow_text(self, session: dict[str, object], room_id: str | None = None) -> str:
        glow = self._sword_glow_level(session, room_id)
        if glow >= 2:
            return "Your sword has begun to glow very brightly."
        if glow == 1:
            return "Your sword is glowing with a faint blue glow."
        return ""

    def _open_flame_present(self, session: dict[str, object]) -> bool:
        for code in ("TORCH", "CANDL"):
            if self._object_is_lit(session, code) and self._is_accessible(session, code):
                return True
        return False

    def _next_bat_drop_room(self, session: dict[str, object]) -> str:
        counters = self._session_counters(session)
        index = int(counters.get("bat_drop_index") or 0)
        counters["bat_drop_index"] = index + 1
        return BAT_DROP_ROOMS[index % len(BAT_DROP_ROOMS)]

    def _carousel_random_target(self, session: dict[str, object]) -> str:
        counters = self._session_counters(session)
        index = int(counters.get("carousel_random_index") or 0)
        counters["carousel_random_index"] = index + 1
        return CAROUSEL_RANDOM_TARGETS[index % len(CAROUSEL_RANDOM_TARGETS)]

    def _magnet_random_target(self, session: dict[str, object]) -> str:
        counters = self._session_counters(session)
        index = int(counters.get("magnet_random_index") or 0)
        counters["magnet_random_index"] = index + 1
        return MAGNET_RANDOM_TARGETS[index % len(MAGNET_RANDOM_TARGETS)]

    def _consume_accessible_object(
        self,
        session: dict[str, object],
        code: str,
        inventory: list[str],
        object_locations: dict[str, str],
    ) -> tuple[list[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        if code_key in inventory:
            inventory = [value for value in inventory if value != code_key]
        object_locations[code_key] = "GONE"
        return inventory, object_locations

    def _shift_room_contents(
        self,
        object_locations: dict[str, str],
        source_room: str,
        target_room: str,
        *,
        exclude: Iterable[str] = (),
    ) -> dict[str, str]:
        source_key = str(source_room or "").strip().upper()
        target_key = str(target_room or "").strip().upper()
        blocked = {str(value).strip().upper() for value in exclude if str(value).strip()}
        for code, location in list(object_locations.items()):
            if str(location or "").strip().upper() != source_key:
                continue
            if code in blocked:
                continue
            object_locations[code] = target_key
        return object_locations

    def _carousel_room_oriented(self, flags: set[str]) -> bool:
        return "carousel_flip" in flags

    def _magnet_room_disoriented(self, flags: set[str]) -> bool:
        return "carousel_flip" in flags

    def _special_exit_text(self, session: dict[str, object], room_id: str) -> str | None:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        if room_key == "CAROU":
            if self._carousel_room_oriented(flags):
                return "Exits north, south, east, west, ne, nw, se, sw, exit."
            return ""
        if room_key == "MAGNE":
            if self._magnet_room_disoriented(flags):
                return ""
            return "Exits east, southeast."
        if room_key == "VAIR4" and self._ledge4_collapsed(flags):
            return "Exits launch, land."
        if room_key == "POG":
            return "Exits up, nw, west, se." if "rainbow_solid" in flags else "Exits se."
        if room_key == "ALISM":
            return "Exits east."
        if room_key == "LEDG2":
            return "Exits south, launch, west." if "gnome_door_open" in flags else "Exits south, launch."
        if room_key == "LEDG4":
            if self._ledge4_collapsed(flags):
                return ""
            exits = ["launch"]
            if not self._safe_room_collapsed(flags):
                exits.insert(0, "south")
            if "gnome_door_open" in flags:
                exits.append("west")
            return f"Exits {', '.join(exits)}."
        if room_key == "SAFE" and self._safe_room_collapsed(flags):
            return ""
        return None

    def _complete_transition_with_prefix(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: list[str],
        flags: set[str],
        object_locations: dict[str, str],
        now_unix: int,
        prefix: str = "",
    ) -> BotAppResult:
        entry_prefix, final_room, inventory, flags, object_locations, ended = self._room_entry_transition(
            session,
            room_id,
            inventory,
            flags,
            object_locations,
        )
        if ended:
            self._sessions.pop(str(session.get("peer_id") or "").strip().lower(), None)
            parts = [prefix, entry_prefix]
            return BotAppResult(
                handled=True,
                reply_text=self._compact(" ".join(part for part in parts if part)),
                command_name=self.SPEC.name,
            )
        summary = self._room_summary_for_state(
            session,
            room_id=final_room,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
        )
        self._write_session_state(
            session,
            room_id=final_room,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
            now_unix=now_unix,
        )
        reply = " ".join(part for part in (prefix, entry_prefix, summary) if part)
        return BotAppResult(
            handled=True,
            reply_text=self._compact(reply),
            command_name=self.SPEC.name,
        )

    def _room_neighbors(
        self,
        session: dict[str, object],
        room_id: str,
        *,
        forbidden_rooms: frozenset[str] | set[str] | None = None,
    ) -> list[str]:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        room = ROOMS.get(room_key)
        if room is None:
            return []
        blocked = {str(value).strip().upper() for value in (forbidden_rooms or set()) if str(value).strip()}
        if room_key == "MAGNE":
            return sorted(target for target in {"CMACH", "ALICE"} if target in ROOMS and target not in blocked)
        if room_key == "CAROU":
            targets = set(CAROUSEL_RANDOM_TARGETS)
            if self._carousel_room_oriented(self._session_flags(session)):
                targets.add("PASS3")
            return sorted(target for target in targets if target in ROOMS and target not in blocked)
        neighbors: list[str] = []
        for exit_row in room.exits:
            kind = str(exit_row.get("kind") or "")
            if kind == "room":
                target = str(exit_row.get("target") or "").strip().upper()
            elif kind == "cexit" and self._condition_passes(session, str(exit_row.get("condition") or ""), exit_row):
                target = str(exit_row.get("target") or "").strip().upper()
            else:
                continue
            if target not in ROOMS or target in blocked:
                continue
            neighbors.append(target)
        return sorted(dict.fromkeys(neighbors))

    def _shortest_room_path(
        self,
        session: dict[str, object],
        start_room: str,
        goal_room: str,
        *,
        forbidden_rooms: frozenset[str] | set[str] | None = None,
    ) -> list[str]:
        start_key = str(start_room or START_ROOM).strip().upper() or START_ROOM
        goal_key = str(goal_room or START_ROOM).strip().upper() or START_ROOM
        if start_key not in ROOMS or goal_key not in ROOMS:
            return []
        blocked = {str(value).strip().upper() for value in (forbidden_rooms or set()) if str(value).strip()}
        if start_key in blocked or goal_key in blocked:
            return []
        if start_key == goal_key:
            return [start_key]
        queue: list[list[str]] = [[start_key]]
        seen = {start_key}
        while queue:
            path = queue.pop(0)
            tail = path[-1]
            for neighbor in self._room_neighbors(session, tail, forbidden_rooms=blocked):
                if neighbor in seen:
                    continue
                next_path = [*path, neighbor]
                if neighbor == goal_key:
                    return next_path
                seen.add(neighbor)
                queue.append(next_path)
        return []

    def _format_object_list(self, codes: Iterable[str]) -> str:
        labels = [object_name(code) for code in codes if str(code or "").strip()]
        if not labels:
            return ""
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return f"{labels[0]} and {labels[1]}"
        return f"{', '.join(labels[:-1])}, and {labels[-1]}"

    def _visible_room_treasures(
        self,
        session: dict[str, object],
        room_id: str,
        inventory: Iterable[str],
        flags: set[str],
        object_locations: dict[str, str],
    ) -> list[str]:
        ghost = self._ephemeral_session(
            session,
            room_id=room_id,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
        )
        visible = self._visible_top_level_objects(ghost, room_id)
        return [code for code in visible if code not in {"THIEF", "STILL"} and self._is_treasure(code)]

    def _thief_flee_room(
        self,
        session: dict[str, object],
        room_id: str,
        flags: set[str],
        object_locations: dict[str, str],
    ) -> str:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        path_home = self._shortest_room_path(
            session,
            room_key,
            THIEF_HOME_ROOM,
            forbidden_rooms=THIEF_FORBIDDEN_ROOMS,
        )
        if len(path_home) > 1:
            return path_home[1]
        neighbors = self._room_neighbors(session, room_key, forbidden_rooms=THIEF_FORBIDDEN_ROOMS)
        if not neighbors:
            return room_key
        longest = ""
        longest_distance = -1
        for candidate in neighbors:
            path = self._shortest_room_path(
                session,
                candidate,
                room_key,
                forbidden_rooms=THIEF_FORBIDDEN_ROOMS,
            )
            distance = len(path)
            if distance > longest_distance:
                longest = candidate
                longest_distance = distance
        return longest or neighbors[0]

    def _thief_entry_event(
        self,
        session: dict[str, object],
        room_id: str,
        inventory: list[str],
        flags: set[str],
        object_locations: dict[str, str],
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        if "thief_defeated" in flags:
            return "", inventory, flags, object_locations

        thief_room = str(object_locations.get("THIEF") or "").strip().upper()
        if thief_room not in ROOMS:
            return "", inventory, flags, object_locations

        moved_in = False
        if room_key != THIEF_HOME_ROOM and room_key not in THIEF_FORBIDDEN_ROOMS and thief_room not in THIEF_FORBIDDEN_ROOMS:
            carry_treasure = any(self._is_treasure(code) for code in inventory)
            loose_treasure = self._visible_room_treasures(session, room_key, inventory, flags, object_locations)
            if thief_room != room_key and (carry_treasure or loose_treasure):
                path_to_player = self._shortest_room_path(
                    session,
                    thief_room,
                    room_key,
                    forbidden_rooms=THIEF_FORBIDDEN_ROOMS,
                )
                if len(path_to_player) > 1:
                    thief_room = path_to_player[1]
                    object_locations["THIEF"] = thief_room
                    object_locations["STILL"] = "THIEF"
                    moved_in = thief_room == room_key
            elif thief_room != room_key:
                counters = self._session_counters(session)
                neighbors = self._room_neighbors(session, thief_room, forbidden_rooms=THIEF_FORBIDDEN_ROOMS)
                if neighbors:
                    patrol_index = int(counters.get("thief_patrol_index") or 0)
                    thief_room = neighbors[patrol_index % len(neighbors)]
                    counters["thief_patrol_index"] = patrol_index + 1
                    object_locations["THIEF"] = thief_room
                    object_locations["STILL"] = "THIEF"
                    moved_in = thief_room == room_key

        if str(object_locations.get("THIEF") or "").strip().upper() != room_key:
            return "", inventory, flags, object_locations

        carried_loot = [code for code in inventory if self._is_treasure(code)]
        floor_loot = self._visible_room_treasures(session, room_key, inventory, flags, object_locations)
        if carried_loot or floor_loot:
            inventory = [code for code in inventory if code not in set(carried_loot)]
            for code in carried_loot:
                object_locations[code] = "THIEF"
            for code in floor_loot:
                object_locations[code] = "THIEF"
            object_locations["STILL"] = "THIEF"
            flee_room = self._thief_flee_room(session, room_key, flags, object_locations)
            if flee_room in ROOMS and flee_room != room_key:
                object_locations["THIEF"] = flee_room
            carried_text = self._format_object_list(carried_loot)
            floor_text = self._format_object_list(floor_loot)
            if carried_text and floor_text:
                return (
                    f"The thief slips out of the shadows, relieves you of {carried_text}, scoops up {floor_text}, and vanishes into the side passages.",
                    inventory,
                    flags,
                    object_locations,
                )
            if carried_text:
                return (
                    f"The thief slips out of the shadows, relieves you of {carried_text}, and vanishes into the side passages.",
                    inventory,
                    flags,
                    object_locations,
                )
            return (
                f"The thief scoops up {floor_text} and vanishes into the side passages.",
                inventory,
                flags,
                object_locations,
            )

        if moved_in:
            return (
                "A suspicious-looking thief slips into the room and watches you warily.",
                inventory,
                flags,
                object_locations,
            )

        return "", inventory, flags, object_locations

    def _apply_treasure_room_entry(
        self,
        session: dict[str, object],
        room_id: str,
        flags: set[str],
        object_locations: dict[str, str],
    ) -> tuple[str, set[str], dict[str, str]]:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        if room_key != "TREAS" or "thief_defeated" in flags:
            return "", flags, object_locations
        if object_locations.get("THIEF") == room_key:
            return "", flags, object_locations
        object_locations["THIEF"] = room_key
        object_locations["STILL"] = "THIEF"
        stolen: list[str] = []
        for code, location in list(object_locations.items()):
            if code in {"THIEF", "STILL"}:
                continue
            if str(location or "").strip().upper() != room_key:
                continue
            if not self._is_treasure(code):
                continue
            object_locations[code] = "THIEF"
            stolen.append(code)
        message = (
            "You hear a scream of anguish as you violate the robber's hideaway. "
            "Using passages unknown to you, he rushes to its defense."
        )
        if stolen:
            message += " The thief gestures mysteriously, and the treasures in the room suddenly vanish."
        return message, flags, object_locations

    def _room_entry_transition(
        self,
        session: dict[str, object],
        room_id: str,
        inventory: list[str],
        flags: set[str],
        object_locations: dict[str, str],
    ) -> tuple[str, str, list[str], set[str], dict[str, str], bool]:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        prefix_parts: list[str] = []

        if room_key == "BATS" and "GARLI" not in set(inventory):
            room_key = self._next_bat_drop_room(session)
            prefix_parts.append(
                "A deranged giant vampire bat swoops down from his belfry and lifts you away...."
            )

        if room_key == "CAROU" and "carousel_zoom" in flags:
            return (
                "According to Prof. TAA of MIT Tech, the rapidly changing magnetic fields in the room are so intense as to cause you to be electrocuted. In any event, something just killed you. zork: session ended. Send 'zork' to start again.",
                room_key,
                inventory,
                flags,
                object_locations,
                True,
            )
        if room_key == "MAGNE" and self._magnet_room_disoriented(flags):
            if "carousel_zoom" in flags:
                return (
                    "According to Prof. TAA of MIT Tech, the rapidly changing magnetic fields in the room are so intense as to cause you to be electrocuted. In any event, something just killed you. zork: session ended. Send 'zork' to start again.",
                    room_key,
                    inventory,
                    flags,
                    object_locations,
                    True,
                )
            prefix_parts.append("As you enter, your compass starts spinning wildly.")

        if room_key in GNOME_LEDGE_ROOMS and "gnome_door_open" not in flags:
            prior_room = str(object_locations.get("GNOME") or "").strip().upper()
            if prior_room != room_key:
                prefix_parts.append(
                    "A volcano gnome seems to walk straight out of the wall and says: 'I have a very busy appointment schedule and little time to waste on trespassers, but for a small fee, I'll show you the way out.'"
                )
            object_locations["GNOME"] = room_key
            counters = self._session_counters(session)
            counters["gnome_nervous_turns"] = 1
            counters["gnome_depart_turns"] = 0

        if room_key == "TREAS":
            treas_reply, flags, object_locations = self._apply_treasure_room_entry(session, room_key, flags, object_locations)
            if treas_reply:
                prefix_parts.append(treas_reply)

        thief_reply, inventory, flags, object_locations = self._thief_entry_event(
            session,
            room_key,
            inventory,
            flags,
            object_locations,
        )
        if thief_reply:
            prefix_parts.append(thief_reply)

        if room_key == "RIVR4" and "BUOY" in set(inventory) and "buoy_feel_noticed" not in flags:
            flags.add("buoy_feel_noticed")
            prefix_parts.append("Something seems funny about the feel of the buoy.")

        if room_key == "BOOM":
            ghost = self._ephemeral_session(
                session,
                room_id=room_key,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            if self._open_flame_present(ghost):
                return (
                    "Oh dear. It appears that the smell coming from this room was coal gas. "
                    "Carrying an open flame in here was a catastrophically bad plan. "
                    "BOOOOOOOOOOOM. zork: session ended. Send 'zork' to start again.",
                    room_key,
                    inventory,
                    flags,
                    object_locations,
                    True,
                )

        return (" ".join(part for part in prefix_parts if part).strip(), room_key, inventory, flags, object_locations, False)

    def _complete_transition(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: list[str],
        flags: set[str],
        object_locations: dict[str, str],
        now_unix: int,
    ) -> BotAppResult:
        return self._complete_transition_with_prefix(
            session,
            room_id=room_id,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
            now_unix=now_unix,
        )

    def _boat_room(self, session: dict[str, object]) -> str:
        return str(self._object_locations(session).get("RBOAT") or "").strip().upper()

    def _aboard_boat(self, session: dict[str, object]) -> bool:
        return "aboard_boat" in self._session_flags(session)

    def _is_river_room(self, room_id: str) -> bool:
        return str(room_id or "").strip().upper().startswith("RIVR")

    def _has_launch_exit(self, room_id: str) -> bool:
        room = ROOMS.get(str(room_id or START_ROOM).strip().upper())
        if room is None:
            return False
        return any(str(row.get("direction") or "").strip().upper() == "LAUNC" for row in room.exits)

    def _boat_tripwire(self, session: dict[str, object], room_id: str | None = None) -> bool:
        room_key = str(room_id or session.get("room") or START_ROOM).strip().upper() or START_ROOM
        boat_room = self._boat_room(session)
        inventory = set(self._session_inventory(session))
        return self._aboard_boat(session) or boat_room == room_key or "RBOAT" in inventory

    def _bucket_room(self, session: dict[str, object]) -> str:
        return str(self._object_locations(session).get("BUCKE") or "").strip().upper()

    def _aboard_bucket(self, session: dict[str, object]) -> bool:
        return "aboard_bucket" in self._session_flags(session)

    def _shaft_basket_room(self, session: dict[str, object]) -> str:
        return str(self._object_locations(session).get("TBASK") or "").strip().upper()

    def _shaft_basket_here(self, session: dict[str, object], room_id: str | None = None) -> bool:
        room_key = str(room_id or session.get("room") or START_ROOM).strip().upper() or START_ROOM
        return self._shaft_basket_room(session) == room_key

    def _balloon_room(self, session: dict[str, object]) -> str:
        return str(self._object_locations(session).get("BALLO") or "").strip().upper()

    def _aboard_balloon(self, session: dict[str, object]) -> bool:
        return "aboard_balloon" in self._session_flags(session)

    def _balloon_tied_room(self, session: dict[str, object]) -> str:
        flags = self._session_flags(session)
        if "balloon_tied_ledg2" in flags:
            return "LEDG2"
        if "balloon_tied_ledg4" in flags:
            return "LEDG4"
        return ""

    def _balloon_fuel_code(self, session: dict[str, object]) -> str:
        for code, location in self._object_locations(session).items():
            if str(location or "").strip().upper() == "RECEP":
                return str(code or "").strip().upper()
        return ""

    def _balloon_burn_turns(self, session: dict[str, object]) -> int:
        counters = self._session_counters(session)
        try:
            return max(0, int(counters.get("balloon_burn_turns") or 0))
        except (TypeError, ValueError):
            return 0

    def _balloon_inflated(self, session: dict[str, object]) -> bool:
        return "balloon_inflated" in self._session_flags(session) or self._balloon_burn_turns(session) > 0

    def _safe_room_collapsed(self, session: dict[str, object] | set[str]) -> bool:
        if isinstance(session, set):
            return "safe_room_collapsed" in session
        return "safe_room_collapsed" in self._session_flags(session)

    def _ledge4_collapsed(self, session: dict[str, object] | set[str]) -> bool:
        if isinstance(session, set):
            return "ledge4_collapsed" in session
        return "ledge4_collapsed" in self._session_flags(session)

    def _turn_event_result(
        self,
        session: dict[str, object],
        *,
        room_id: str,
        inventory: list[str],
        flags: set[str],
        object_locations: dict[str, str],
        now_unix: int,
        message: str,
        ended: bool = False,
    ) -> BotAppResult:
        peer_id = str(session.get("peer_id") or "").strip().lower()
        if ended:
            self._sessions.pop(peer_id, None)
            return BotAppResult(
                handled=True,
                reply_text=self._compact(message),
                command_name=self.SPEC.name,
            )
        self._write_session_state(
            session,
            room_id=room_id,
            inventory=inventory,
            flags=flags,
            object_locations=object_locations,
            now_unix=now_unix,
        )
        return BotAppResult(
            handled=True,
            reply_text=self._compact(f"{message} {self._room_summary(session, room_id)}"),
            command_name=self.SPEC.name,
        )

    def _handle_pending_turn_events(
        self,
        session: dict[str, object],
        *,
        now_unix: int,
    ) -> BotAppResult | None:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        counters = self._session_counters(session)

        fuse_turns = int(counters.get("fuse_turns") or 0)
        if fuse_turns > 0:
            counters["fuse_turns"] = fuse_turns - 1
            if counters["fuse_turns"] <= 0:
                flags.discard("fuse_lit")
                object_locations["BRICK"] = "GONE"
                object_locations["FUSE"] = "GONE"
                if room_id == "SAFE":
                    return self._turn_event_result(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        message=(
                            "Now you've done it. It seems that the brick has other properties than weight, namely the ability to blow you to smithereens. "
                            "zork: session ended. Send 'zork' to start again."
                        ),
                        ended=True,
                    )
                flags.add("safe_blown")
                counters["safe_collapse_turns"] = 5
                return self._turn_event_result(
                    session,
                    room_id=room_id,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                    message="There is an explosion nearby.",
                )

        safe_collapse_turns = int(counters.get("safe_collapse_turns") or 0)
        if safe_collapse_turns > 0:
            counters["safe_collapse_turns"] = safe_collapse_turns - 1
            if counters["safe_collapse_turns"] <= 0:
                flags.add("safe_room_collapsed")
                counters["ledge_collapse_turns"] = 8
                if room_id == "SAFE":
                    return self._turn_event_result(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        message=(
                            "The room trembles and 50,000 pounds of rock fall on you, turning you into a pancake. "
                            "zork: session ended. Send 'zork' to start again."
                        ),
                        ended=True,
                    )
                return self._turn_event_result(
                    session,
                    room_id=room_id,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                    message=(
                        "You may recall your recent explosion. Well, probably as a result of that, you hear an ominous rumbling, "
                        "as if one of the rooms in the dungeon had collapsed."
                    ),
                )

        ledge_collapse_turns = int(counters.get("ledge_collapse_turns") or 0)
        if ledge_collapse_turns > 0:
            counters["ledge_collapse_turns"] = ledge_collapse_turns - 1
            if counters["ledge_collapse_turns"] <= 0 and "ledge4_collapsed" not in flags:
                flags.add("ledge4_collapsed")
                if room_id == "LEDG4":
                    if "aboard_balloon" in flags and str(object_locations.get("BALLO") or "").strip().upper() == "LEDG4":
                        if self._balloon_tied_room(session) == "LEDG4":
                            flags.discard("balloon_tied_ledg2")
                            flags.discard("balloon_tied_ledg4")
                            flags.discard("balloon_inflated")
                            flags.discard("aboard_balloon")
                            counters["balloon_burn_turns"] = 0
                            object_locations["BALLO"] = "GONE"
                            object_locations["DBALL"] = "VLBOT"
                            return self._turn_event_result(
                                session,
                                room_id=room_id,
                                inventory=inventory,
                                flags=flags,
                                object_locations=object_locations,
                                now_unix=now_unix,
                                message=(
                                    "The ledge collapses, probably as a result of the explosion. A large chunk of it, which is attached to the hook, drags you down "
                                    "to the ground. Fatally. zork: session ended. Send 'zork' to start again."
                                ),
                                ended=True,
                            )
                        object_locations["BALLO"] = "VAIR4"
                        return self._turn_event_result(
                            session,
                            room_id="VAIR4",
                            inventory=inventory,
                            flags=flags,
                            object_locations=object_locations,
                            now_unix=now_unix,
                            message="The ledge collapses, leaving you with no place to land.",
                        )
                    return self._turn_event_result(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        message=(
                            "The force of the explosion has caused the ledge to collapse belatedly. "
                            "zork: session ended. Send 'zork' to start again."
                        ),
                        ended=True,
                    )
                return self._turn_event_result(
                    session,
                    room_id=room_id,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                    message="The ledge collapses, giving you a narrow escape.",
                )

        gnome_room = str(object_locations.get("GNOME") or "").strip().upper()
        if gnome_room == room_id and room_id in GNOME_LEDGE_ROOMS and "gnome_door_open" not in flags:
            nervous_turns = int(counters.get("gnome_nervous_turns") or 0)
            if nervous_turns > 0:
                counters["gnome_nervous_turns"] = nervous_turns - 1
                if counters["gnome_nervous_turns"] <= 0:
                    counters["gnome_depart_turns"] = 5
                    return self._turn_event_result(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        message="The gnome appears increasingly nervous.",
                    )
            depart_turns = int(counters.get("gnome_depart_turns") or 0)
            if depart_turns > 0:
                counters["gnome_depart_turns"] = depart_turns - 1
                if counters["gnome_depart_turns"] <= 0:
                    object_locations["GNOME"] = "GONE"
                    return self._turn_event_result(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        message=(
                            "The gnome glances at his watch. 'Oops. I'm late for an appointment!' "
                            "He disappears, leaving you alone on the ledge."
                        ),
                    )

        return None

    def _balloon_fuel_duration(self, code: str) -> int:
        return int(BALLOON_FUEL_TURNS.get(str(code or "").strip().upper(), DEFAULT_BALLOON_FUEL_TURNS))

    def _default_board_target(self, session: dict[str, object]) -> str:
        if self._is_accessible(session, "RBOAT"):
            return "boat"
        if self._is_accessible(session, "IBOAT"):
            return "boat"
        if self._is_accessible(session, "BALLO"):
            return "balloon"
        if self._is_accessible(session, "DBALL"):
            return "balloon"
        if self._is_accessible(session, "BUCKE"):
            return "bucket"
        return "boat"

    def _is_accessible(self, session: dict[str, object], code: str, *, include_room: bool = True, include_inventory: bool = True) -> bool:
        code_key = str(code or "").strip().upper()
        if not code_key:
            return False
        if code_key == "FBASK":
            return False
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        inventory = set(self._session_inventory(session))
        object_locations = self._object_locations(session)
        location = str(object_locations.get(code_key) or "").strip().upper()
        location_container = self._location_container_code(location)
        if include_inventory and code_key in inventory:
            return True
        if include_room and location == room_id and self._room_object_visible(code_key, room_id, flags, object_locations):
            return True
        if location and location_container in inventory and self._container_open(location_container, flags):
            return True
        if location and include_room and location_container in self._visible_top_level_objects(session, room_id) and self._container_open(location_container, flags):
            return True
        if location == "RECEP" and self._is_accessible(session, "RECEP", include_room=include_room, include_inventory=include_inventory):
            return True
        if location == "TROLL" and room_id == "MTROL" and self._container_open("TROLL", flags):
            return True
        return False

    def _special_case_object(self, session: dict[str, object], action: str, words: list[str]) -> str | None:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        word_set = set(words)
        if not word_set:
            return None
        if "mailbox" in word_set or "mailb" in word_set:
            return "MAILB"
        if "leaflet" in word_set or "pamph" in word_set or "bookl" in word_set or "adver" in word_set:
            return "ADVER"
        if "gate" in word_set or "gates" in word_set:
            if room_id == "LLD1":
                return "GATES"
            if room_id == "DAM":
                return "DAM"
        if room_id == "SAFE" and ("slot" in word_set or "hole" in word_set):
            return "SSLOT"
        if room_id == "SAFE" and ("safe" in word_set or "box" in word_set):
            return "SAFE"
        if room_id == "CAGED" and ("cage" in word_set or "bars" in word_set or "iron" in word_set):
            return "CAGE"
        if "robot" in word_set or "robby" in word_set:
            return "ROBOT"
        if room_id == "ICY" and ("glacier" in word_set or "ice" in word_set or "icicle" in word_set):
            return "ICE"
        if room_id in {"MIRR1", "MIRR2"} and ("mirror" in word_set or "glass" in word_set):
            return "REFL1" if room_id == "MIRR1" else "REFL2"
        if room_id == "MACHI" and ("machine" in word_set or "lid" in word_set or "dryer" in word_set or "pdp10" in word_set):
            return "MACHI"
        if "bolt" in word_set or "nut" in word_set:
            return "BOLT"
        if "bubble" in word_set:
            return "BUBBL"
        if room_id == "CMACH":
            if "round" in word_set or "circle" in word_set or "circular" in word_set:
                return "RNBUT"
            if "square" in word_set or "squar" in word_set:
                return "SQBUT"
            if "triangle" in word_set or "triangular" in word_set or "trian" in word_set:
                return "TRBUT"
        if "button" in word_set or "buttons" in word_set or "switch" in word_set or "switches" in word_set:
            if room_id == "CMACH":
                if "round" in word_set:
                    return "RNBUT"
                if "square" in word_set or "squar" in word_set:
                    return "SQBUT"
                if "triangle" in word_set or "triangular" in word_set or "trian" in word_set:
                    return "TRBUT"
            if "yellow" in word_set or "yello" in word_set:
                return "YBUTT"
            if "brown" in word_set:
                return "BRBUT"
            if "blue" in word_set:
                return "BLBUT"
            if "red" in word_set:
                return "RBUTT"
        if "cake" in word_set or "icing" in word_set or "eatme" in word_set or "eatm" in word_set:
            if "orange" in word_set or "orang" in word_set:
                return "ORICE"
            if "red" in word_set:
                return "RDICE"
            if "blue" in word_set or "ecch" in word_set:
                return "BLICE"
            if "eatme" in word_set or "eatm" in word_set or action == "eat":
                if self._is_accessible(session, "ECAKE"):
                    return "ECAKE"
        if "ghost" in word_set or "spirit" in word_set or "spirits" in word_set or "fiend" in word_set or "fiends" in word_set:
            return "GHOST"
        if "thief" in word_set or "robber" in word_set or "crook" in word_set or "bandit" in word_set or "bagman" in word_set:
            return "THIEF"
        if "candles" in word_set or "candle" in word_set:
            return "CANDL"
        if "torch" in word_set:
            return "TORCH"
        if "shovel" in word_set:
            return "SHOVE"
        if "statue" in word_set or "sculpture" in word_set or "sculp" in word_set:
            return "STATU"
        if "guano" in word_set or "turd" in word_set or "turds" in word_set or "crap" in word_set or "shit" in word_set:
            return "GUANO"
        if "stiletto" in word_set or "stilletto" in word_set:
            return "STILL"
        if "bat" in word_set or "vampire" in word_set:
            return "BAT"
        if "book" in word_set or "bible" in word_set or "goodbook" in word_set:
            return "BOOK"
        if "bell" in word_set:
            return "BELL"
        if room_id == "MAINT" and ("leak" in word_set or "drip" in word_set or "hole" in word_set):
            return "LEAK"
        if room_id in {"TSHAF", "BSHAF"} and ("chain" in word_set or "basket" in word_set or "dumbwaiter" in word_set or "dumbw" in word_set):
            if action in {"raise", "lower"} or self._shaft_basket_here(session, room_id):
                return "TBASK"
        if "putty" in word_set or "gunk" in word_set or "glue" in word_set or "material" in word_set:
            return "PUTTY"
        if "window" in word_set or "windo" in word_set:
            if room_id == "KITCH":
                return "WIND2"
            if room_id == "EHOUS":
                return "WIND1"
        if "grating" in word_set or "grate" in word_set or "grati" in word_set:
            if room_id == "MGRAT":
                return "GRAT2"
            return "GRAT1"
        if "rug" in word_set or "carpet" in word_set:
            return "RUG"
        if "leaves" in word_set or "leaf" in word_set or "pile" in word_set:
            return "LEAVE"
        if "troll" in word_set:
            return "TROLL"
        if "cyclops" in word_set or "monster" in word_set or "one" in word_set or "eyed" in word_set:
            return "CYCLO"
        if "axe" in word_set:
            return "AXE"
        if "lamp" in word_set or "lantern" in word_set or "lante" in word_set:
            return "LAMP"
        if "label" in word_set or "finep" in word_set:
            if "blue" in word_set or "bluel" in word_set:
                if self._is_accessible(session, "BLABE"):
                    return "BLABE"
            if self._is_accessible(session, "LABEL"):
                return "LABEL"
            if self._is_accessible(session, "BLABE"):
                return "BLABE"
            return "LABEL"
        if "buoy" in word_set:
            return "BUOY"
        if "receptacle" in word_set or "burner" in word_set or "recep" in word_set:
            return "RECEP"
        if "wire" in word_set or "braided" in word_set:
            return "BROPE"
        if "hook" in word_set:
            if room_id == "LEDG2":
                return "HOOK1"
            if room_id == "LEDG4":
                return "HOOK2"
        if "balloon" in word_set or "basket" in word_set or "wicker" in word_set:
            if self._is_accessible(session, "BALLO"):
                return "BALLO"
            if self._is_accessible(session, "DBALL"):
                return "DBALL"
        if "boat" in word_set:
            if action == "board":
                if self._is_accessible(session, "RBOAT"):
                    return "RBOAT"
                if self._is_accessible(session, "IBOAT"):
                    return "IBOAT"
            if self._is_accessible(session, "RBOAT"):
                return "RBOAT"
            if self._is_accessible(session, "IBOAT"):
                return "IBOAT"
            if self._is_accessible(session, "DBOAT"):
                return "DBOAT"
        if "railing" in word_set or "rail" in word_set:
            return "RAILI"
        if "rainbow" in word_set:
            return "RAINB"
        if "keys" in word_set or "key" in word_set or "skeleton" in word_set:
            return "KEYS"
        if "paper" in word_set or "newspaper" in word_set or "news" in word_set:
            return "PAPER"
        if "door" in word_set or "trapdoor" in word_set or "trap" in word_set:
            if "front" in word_set:
                return "FDOOR"
            if "stone" in word_set:
                return "SDOOR"
            if "wooden" in word_set or "woode" in word_set:
                return "WDOOR"
            if room_id in {"LROOM", "CELLA"}:
                if room_id == "LROOM":
                    if action in {"read", "examine", "look"} and "trap" not in word_set and "rug_moved" not in flags and "trap_door_open" not in flags:
                        return "WDOOR"
                    if "trap" in word_set or action in {"open", "close", "unlock", "move"}:
                        return "DOOR"
                    if "rug_moved" in flags or "trap_door_open" in flags:
                        return "DOOR"
                    return "WDOOR"
                return "TDOOR"
            if room_id == "WHOUS":
                return "FDOOR"
            if room_id == "TEMP1":
                return "SDOOR"
        return None

    def _target_may_be_addressed(self, session: dict[str, object], code: str, action: str) -> bool:
        code_key = str(code or "").strip().upper()
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if self._is_accessible(session, code_key):
            return True
        if code_key == "RAILI" and room_id == "DOME":
            return True
        if code_key == "DOOR" and room_id == "LROOM":
            return True
        if code_key == "TDOOR" and room_id == "CELLA":
            return True
        if code_key == "WDOOR" and room_id == "LROOM":
            return True
        if code_key == "FDOOR" and room_id == "WHOUS":
            return True
        if code_key == "MAILB" and room_id == "WHOUS":
            return True
        if code_key == "TBASK" and room_id in {"TSHAF", "BSHAF"} and action in {"raise", "lower"}:
            return True
        if code_key == "WIND1" and room_id == "EHOUS":
            return True
        if code_key == "WIND2" and room_id == "KITCH":
            return True
        if code_key in {"GRAT1", "GRAT2"} and room_id in {"CLEAR", "MGRAT"} and self._is_accessible(session, code_key):
            return True
        return False

    def _resolve_object(self, session: dict[str, object], raw_target: str, action: str) -> str | None:
        words = self._clean_words(raw_target)
        if not words:
            return None
        special = self._special_case_object(session, action, words)
        if special:
            return special if self._target_may_be_addressed(session, special, action) else None
        candidates: list[str] = []
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        candidates.extend(self._visible_top_level_objects(session, room_id))
        candidates.extend(self._session_inventory(session))
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        visible_top_level = self._visible_top_level_objects(session, room_id)
        inventory_set = set(self._session_inventory(session))
        for code, location in object_locations.items():
            location_container = self._location_container_code(location)
            if location_container in inventory_set and self._container_open(location_container, flags):
                candidates.append(code)
            if location_container in visible_top_level and self._container_open(location_container, flags):
                candidates.append(code)
            if str(location or "").strip().upper() == "RECEP" and self._is_accessible(session, "RECEP"):
                candidates.append(code)
        unique_candidates = sorted({code for code in candidates if code in OBJECTS})
        best_score = -1
        best_code: str | None = None
        query_set = set(words)
        query_text = " ".join(words)
        for code in unique_candidates:
            item = OBJECTS.get(code)
            if item is None:
                continue
            vocab = set(item.vocabulary)
            if not self._query_matches_vocabulary(query_set, vocab):
                continue
            name_words = self._clean_words(item.name)
            score = len(query_set)
            if name_words and query_text == " ".join(name_words):
                score += 20
            if code in self._session_inventory(session):
                score += 3
            if code in self._visible_top_level_objects(session, room_id):
                score += 2
            if score > best_score:
                best_score = score
                best_code = code
        return best_code

    def _object_is_lit(self, session: dict[str, object], code: str) -> bool:
        flags = self._session_flags(session)
        code_key = str(code or "").strip().upper()
        if code_key == "LAMP":
            return "lamp_lit" in flags
        if code_key == "TORCH":
            return "torch_unlit" not in flags
        if code_key == "CANDL":
            return "candles_unlit" not in flags
        return False

    def _has_light(self, session: dict[str, object]) -> bool:
        for code in ("LAMP", "TORCH", "CANDL"):
            if self._object_is_lit(session, code) and self._is_accessible(session, code):
                return True
        return False

    def _room_is_dark(self, session: dict[str, object], room_id: str) -> bool:
        room_key = str(room_id or START_ROOM).strip().upper()
        room = ROOMS.get(room_key)
        if room is None:
            return False
        if room_key in NATURALLY_LIT_ROOMS:
            return False
        if room_key == "MAINT" and "maintenance_lights_on" in self._session_flags(session):
            return False
        return (not room.lit) and (not self._has_light(session))

    def _object_presence_text(self, code: str, session: dict[str, object]) -> str:
        code_key = str(code or "").strip().upper()
        item = OBJECTS.get(code_key)
        if item is None:
            return ""
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key == "DAM":
            return ""
        if code_key in {"SQBUT", "RNBUT", "TRBUT"}:
            return ""
        if code_key == "ICE":
            return "" if "glacier_melted" in self._session_flags(session) else "A mass of ice fills the western half of the room."
        if code_key in {"REFL1", "REFL2"}:
            return "The mirror is broken into many pieces." if "mirror_broken" in self._session_flags(session) else "An enormous mirror fills the south wall."
        if code_key == "MACHI":
            return "A large machine squats here with its lid open." if "machine_open" in self._session_flags(session) else "A large machine squats here with its lid closed."
        if code_key == "MSWIT":
            return "A switch protrudes from the machine."
        if code_key == "SAFE":
            if self._safe_room_collapsed(session):
                return "The way to the south is blocked by debris from an explosion."
            return (
                "A rusty old box is set in the wall, its door blown away."
                if "safe_blown" in self._session_flags(session)
                else "A rusty old box is imbedded in the wall."
            )
        if code_key == "TCASE":
            contents = self._container_contents(session, "TCASE")
            if not contents:
                return "There is a trophy case here."
            labels = [object_name(value) for value in contents[:3]]
            summary = ", ".join(labels)
            if len(contents) > 3:
                summary += ", ..."
            return f"There is a trophy case here containing {summary}."
        if code_key == "SSLOT":
            return "" if "safe_blown" in self._session_flags(session) else "An oblong hole has been chipped out of the front of the box."
        if code_key == "FUSE":
            if "fuse_lit" in self._session_flags(session):
                return "A fuse burns with an unhealthy enthusiasm."
            return ""
        if code_key == "GATES":
            return (
                "A black gateway stands open."
                if "lld_open" in self._session_flags(session)
                else "A black gateway stands here, crowded with jeering spirits."
            )
        if code_key == "BOLT":
            return "A large metal bolt protrudes from the control panel."
        if code_key == "BUBBL":
            return (
                "A small green bubble glows above the bolt."
                if "gate_enabled" in self._session_flags(session)
                else "A small green bubble sits dark above the bolt."
            )
        if code_key in {"BLBUT", "BRBUT", "RBUTT", "YBUTT"}:
            return ""
        if code_key == "LEAK":
            return "Water spurts angrily from a ruptured pipe in the east wall." if "maintenance_leak_active" in self._session_flags(session) else ""
        if code_key == "GHOST":
            return "" if "lld_open" in self._session_flags(session) else "Evil spirits swirl near the gate."
        if code_key == "BAT":
            inventory = set(self._session_inventory(session))
            if room_id == "BATS" and "GARLI" in inventory:
                return "A large vampire bat clings to the ceiling, obviously deranged and holding his nose."
            return ""
        if code_key == "THIEF":
            if "thief_defeated" in self._session_flags(session):
                return "There is a suspicious-looking individual lying unconscious on the ground."
            return "There is a suspicious-looking individual, holding a bag and a vicious-looking stiletto, leaning against one wall."
        if code_key == "TORCH":
            if "torch_burned_out" in self._session_flags(session):
                return "There is a burned out ivory torch here."
            return "There is a flaming ivory torch here." if self._object_is_lit(session, "TORCH") else "There is an ivory torch here."
        if code_key == "CANDL":
            return "There are two burning candles here." if self._object_is_lit(session, "CANDL") else "There are two candles here."
        if code_key == "BALLO":
            fuel_code = self._balloon_fuel_code(session)
            fuel_text = f" A {object_name(fuel_code)} burns in its receptacle." if fuel_code and self._balloon_inflated(session) else ""
            tie_text = " The wire is fastened to a hook in the rock." if self._balloon_tied_room(session) == room_id else ""
            if self._balloon_inflated(session):
                return f"There is a wicker basket here supporting a large inflated cloth balloon.{fuel_text}{tie_text}"
            return f"There is a very large wicker basket here with a cloth bag draped over it.{tie_text}"
        if code_key == "DBALL":
            return "There is a balloon here, broken into pieces."
        if code_key == "POOL":
            if "pool_evaporated" in self._session_flags(session):
                return ""
            return "The leak has submerged the depressed area in a pool of sewage."
        if code_key == "BUOY":
            return "There is a red buoy here, now hanging open." if "buoy_open" in self._session_flags(session) else "There is a red buoy here (probably a warning)."
        if code_key == "LABEL":
            return "A tan label is attached to the boat."
        if code_key == "TROLL":
            if "troll_defeated" in self._session_flags(session):
                return "An unconscious troll is sprawled on the floor."
            return "A nasty-looking troll, brandishing a bloody axe, blocks the passages."
        if code_key == "CYCLO":
            if "cyclops_gone" in self._session_flags(session):
                return "A cyclops-sized hole gapes in the north wall."
            return "A huge cyclops blocks the staircase, looking altogether too interested in adventurers."
        if code_key == "MAILB":
            if "mailbox_open" in self._session_flags(session):
                return "There is a small open mailbox here."
            return item.short_desc or "There is a small mailbox here."
        if code_key in {"WIND1", "WIND2"}:
            if "kitchen_window_open" in self._session_flags(session):
                return "The kitchen window is open."
            return "The kitchen window is slightly ajar."
        if code_key in {"DOOR", "TDOOR"}:
            if "trap_door_open" in self._session_flags(session):
                return "An open trap door yawns here."
            return "A closed trap door is here."
        if code_key in {"GRAT1", "GRAT2"}:
            if "grating_open" in self._session_flags(session):
                return "An open grating is here."
            if "grating_unlocked" in self._session_flags(session):
                return "A closed but unlocked grating is here."
            return "A locked grating is here."
        if code_key == "RAILI":
            return "A wooden railing circles the edge of the dome."
        if code_key == "ROPE" and room_id == "DOME" and "dome_rope_tied" in self._session_flags(session):
            return "A rope is tied to the railing here and hangs into the room below."
        if code_key == "RAINB":
            if "rainbow_solid" in self._session_flags(session):
                return "A solid rainbow spans the falls."
            return "A beautiful rainbow arches over the falls."
        if code_key == "SDOOR":
            if "riddle_solved" in self._session_flags(session):
                return "The great stone door stands open."
            return "A great stone door blocks the east wall."
        if item.short_desc:
            return item.short_desc
        name = object_name(code_key)
        if name:
            return f"You see {name}."
        return ""

    def _dynamic_room_description(self, session: dict[str, object], room_id: str) -> str:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        if room_key == "KITCH":
            state = "open" if "kitchen_window_open" in flags else "slightly ajar"
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(window_state=state)
        if room_key == "BATS":
            if "GARLI" in set(self._session_inventory(session)):
                return (
                    "You are in a small room which has only one door, to the east. "
                    "In the corner of the room on the ceiling is a large vampire bat who is obviously deranged and holding his nose."
                )
            return "You are in a small room which has only one door, to the east."
        if room_key == "CAGED":
            return (
                "You are trapped inside a steel cage, while poisonous gas trickles into the room."
            )
        if room_key == "ICY":
            west_state = (
                "There are passages to the north, east, and west."
                if "glacier_melted" in flags
                else "There are passages to the north and east. A glacier blocks the way west."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(west_state=west_state)
        if room_key == "CAROU":
            bearing_state = (
                ""
                if self._carousel_room_oriented(flags)
                else "Your compass needle spins wildly, and you can't get your bearings."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(bearing_state=bearing_state).strip()
        if room_key == "CMACH":
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key]
        if room_key == "MAGNE":
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key]
        if room_key == "ALITR":
            pool_state = (
                "The leak has filled the depression with a pool of sewage."
                if "pool_evaporated" not in flags
                else "The depressed area is dry now, and a tin of rare spices lies exposed where the pool used to be."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(pool_state=pool_state)
        if room_key == "LLD2":
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key]
        if room_key in {"MIRR1", "MIRR2"}:
            mirror_state = "Unfortunately, you have managed to destroy it by your reckless actions." if "mirror_broken" in flags else ""
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(mirror_state=mirror_state).strip()
        if room_key == "MACHI":
            machine_state = "its lid yawning open beside a chunky switch." if "machine_open" in flags else "its lid shut beside a chunky switch."
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(machine_state=machine_state)
        if room_key == "SAFE":
            if self._safe_room_collapsed(flags):
                return "The way is blocked by debris from an explosion."
            safe_state = (
                "On the far wall is a rusty box, whose door has been blown off."
                if "safe_blown" in flags
                else "Imbedded in the far wall is a rusty old box with an oblong hole chipped out of the front."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(safe_state=safe_state)
        if room_key == "LEDG2":
            west_state = (
                "A narrow chimney slopes down through a small door in the west wall."
                if "gnome_door_open" in flags
                else ""
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(west_state=west_state).strip()
        if room_key == "LEDG4":
            if self._ledge4_collapsed(flags):
                return "The ledge has collapsed and cannot be landed on."
            south_state = "The way to the south is blocked by rubble." if self._safe_room_collapsed(flags) else "There is a small door to the south."
            west_state = (
                "A narrow chimney slopes down through a small door in the west wall."
                if "gnome_door_open" in flags
                else ""
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(south_state=south_state, west_state=west_state).strip()
        if room_key == "LROOM":
            if "trap_door_open" in flags and "rug_moved" in flags:
                center_state = "and a rug lying beside an open trap door"
            elif "trap_door_open" in flags:
                center_state = "and an open trap door at your feet"
            elif "rug_moved" in flags:
                center_state = "and a closed trap door at your feet"
            else:
                center_state = "and a large oriental rug in the center of the room"
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(center_state=center_state)
        if room_key == "CLEAR":
            if "grating_open" in flags:
                grating_state = "There is an open grating, descending into darkness."
            elif "leaves_moved" in flags:
                if "grating_unlocked" in flags:
                    grating_state = "There is a closed grating in the ground."
                else:
                    grating_state = "There is a grating securely fastened into the ground."
            else:
                grating_state = "A pile of leaves lies nearby."
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(grating_state=grating_state)
        if room_key == "MTROL":
            troll_state = (
                "An unconscious troll is sprawled on the floor. All passages are now open."
                if "troll_defeated" in flags
                else "A nasty-looking troll brandishing a bloody axe blocks all passages except west."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(troll_state=troll_state)
        if room_key == "MTORC":
            rope_state = (
                "A large piece of rope descends from the railing above, ending a few feet over your head."
                if "dome_rope_tied" in flags
                else ""
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(rope_state=rope_state).strip()
        if room_key == "DOME":
            rope_state = (
                "Hanging down from the railing is a rope which ends about ten feet above the floor below."
                if "dome_rope_tied" in flags
                else ""
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(rope_state=rope_state).strip()
        if room_key == "FALLS":
            rainbow_state = (
                "A solid rainbow spans the falls."
                if "rainbow_solid" in flags
                else "A beautiful rainbow can be seen over the falls and to the east."
            )
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(rainbow_state=rainbow_state)
        if room_key == "CYCLO":
            if "magic_door_open" in flags:
                cyclops_state = "The cyclops has fled."
                north_state = "On the north side of the room is a cyclops-sized hole in what used to be a solid wall."
            else:
                cyclops_state = "A cyclops, who looks prepared to eat horses, blocks the staircase."
                north_state = ""
            return ROOM_DYNAMIC_DESCRIPTIONS[room_key].format(cyclops_state=cyclops_state, north_state=north_state).strip()
        if room_key == "DAM":
            water_state = (
                "It appears that the dam has been opened since the water level behind it is low and the sluice gates are open. Water is rushing downstream through the gates."
                if "low_tide" in flags
                else "The sluice gates on the dam are closed. Behind the dam, there can be seen a wide lake. A small stream is formed by the runoff from the lake."
            )
            bubble_state = "The green bubble is glowing." if "gate_enabled" in flags else "The green bubble is dark."
            return (
                "You are standing on the top of Flood Control Dam #3, a relic of elder tourism. Paths lead north, south, east, and down. "
                f"{water_state} There is a control panel here with a large metal bolt. {bubble_state}"
            )
        if room_key == "LLD1":
            barrier = (
                "The evil spirits have fled, and the way through the gate lies open."
                if "lld_open" in flags
                else "The way through the gate is barred by evil spirits, who jeer at your attempts to pass."
            )
            return (
                "You are outside a large gateway inscribed 'Abandon every hope, all ye who enter here.' "
                "Through it you can see a desolation, with a pile of mangled corpses in one corner. "
                "Thousands of voices lament some hideous fate. "
                f"{barrier}"
            )
        room = ROOMS.get(room_key)
        if room is None:
            return room_name(room_key)
        return room.long_desc or room.short_name or room.code.title()

    def _room_summary(self, session: dict[str, object], room_id: str, *, explicit_look: bool = False) -> str:
        room_key = str(room_id or START_ROOM).strip().upper() or START_ROOM
        room = ROOMS.get(room_key)
        if room is None:
            return self._compact(f"Unknown room {room_key}.")
        if self._room_is_dark(session, room_key):
            return self._compact("It is pitch black. You are likely to be eaten by a grue.")

        first_visit = not self._seen_room(session, room_key)
        title = room_name(room_key)
        if explicit_look or first_visit:
            desc = self._dynamic_room_description(session, room_key)
            parts = [title + "."]
            if desc and desc.strip().lower() != title.strip().lower():
                parts.append(desc)
        else:
            parts = [title + "."]
        visible_objects = self._visible_top_level_objects(session, room_key)
        presence_texts: list[str] = []
        for code in visible_objects:
            if code in {"FDOOR", "WDOOR", "WIND1", "WIND2", "DOOR", "TDOOR", "GRAT1", "GRAT2"} and not explicit_look and not first_visit:
                continue
            text = self._object_presence_text(code, session)
            if not text:
                continue
            presence_texts.append(text)
        if presence_texts:
            parts.append(" ".join(presence_texts[:4]))

        if self._aboard_boat(session) and self._boat_room(session) == room_key:
            parts.append("You are in the magic boat.")
        if self._aboard_bucket(session) and self._bucket_room(session) == room_key:
            parts.append("You are in the wooden bucket.")

        sword_glow = self._sword_glow_text(session, room_key)
        if sword_glow:
            parts.append(sword_glow)

        special_exits = self._special_exit_text(session, room_key)
        if special_exits is not None:
            if special_exits:
                parts.append(special_exits)
            return self._compact(" ".join(part for part in parts if part))

        exits: list[str] = []
        for exit_row in room.exits:
            direction = str(exit_row.get("direction") or "").strip().upper()
            if not direction:
                continue
            kind = str(exit_row.get("kind") or "")
            if kind == "room":
                exits.append(direction.lower())
                continue
            if kind == "cexit" and self._condition_passes(session, str(exit_row.get("condition") or ""), exit_row):
                exits.append(direction.lower())
        if exits:
            parts.append(f"Exits {', '.join(exits)}.")
        return self._compact(" ".join(part for part in parts if part))

    def _condition_passes(self, session: dict[str, object], condition: str, exit_row: dict[str, object] | None = None) -> bool:
        condition_key = str(condition or "").strip().upper()
        flags = self._session_flags(session)
        inventory = set(self._session_inventory(session))
        if not condition_key:
            return True
        if condition_key == "KITCHEN-WINDOW":
            return "kitchen_window_open" in flags
        if condition_key == "TRAP-DOOR":
            return "trap_door_open" in flags
        if condition_key == "TROLL-FLAG":
            return "troll_defeated" in flags
        if condition_key == "KEY-FLAG":
            return "grating_open" in flags
        if condition_key == "LOW-TIDE":
            return "low_tide" in flags
        if condition_key == "LLD-FLAG":
            return "lld_open" in flags
        if condition_key == "EMPTY-HANDED":
            return not inventory
        if condition_key == "LIGHT-LOAD":
            return len(inventory) <= 2 and "LAMP" in inventory
        if condition_key == "DEFLATE":
            room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
            boat_room = self._boat_room(session)
            return ("RBOAT" not in inventory) and (boat_room != room_id) and ("aboard_boat" not in flags)
        if condition_key == "DOME-FLAG":
            return "dome_rope_tied" in flags
        if condition_key == "GLACIER-FLAG":
            return "glacier_melted" in flags
        if condition_key == "RAINBOW":
            return "rainbow_solid" in flags
        if condition_key == "MAGIC-FLAG":
            return "magic_door_open" in flags
        if condition_key == "CYCLOPS-FLAG":
            return "cyclops_gone" in flags
        if condition_key == "RIDDLE-FLAG":
            return "riddle_solved" in flags
        if condition_key == "EGYPT-FLAG":
            return "COFFI" not in inventory
        if condition_key == "CAROUSEL-FLIP":
            return True
        # Unsupported late-game conditionals stay blocked until ported.
        return False

    def _blocked_exit_message(self, session: dict[str, object], exit_row: dict[str, object]) -> str:
        kind = str(exit_row.get("kind") or "")
        if kind == "nexit":
            message = str(exit_row.get("message") or "").strip()
            return message or "You can't go that way."
        if kind == "unknown":
            return "That route is not fully ported yet."
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if room_id == "CAGED":
            return "You are stopped by the cage and a cloud of poisonous gas."
        condition = str(exit_row.get("condition") or "").strip().upper()
        if condition == "KITCHEN-WINDOW":
            return "The kitchen window is only slightly ajar. Try 'open window'."
        if condition == "TRAP-DOOR":
            return "The trap door is closed."
        if condition == "KEY-FLAG":
            return "The grating is closed."
        if condition == "TROLL-FLAG":
            return "The troll blocks your way."
        if condition == "LOW-TIDE":
            return "The water is too deep for that."
        if condition == "LLD-FLAG":
            return "Some invisible force prevents you from passing through the gate."
        if condition == "RAINBOW":
            return "The rainbow is still only a rainbow, not a bridge."
        if condition == "DOME-FLAG":
            return "You cannot go that way without a rope."
        if condition == "GLACIER-FLAG":
            return "The glacier blocks the way west."
        if condition == "DEFLATE":
            return "The inflated boat is too unwieldy for that narrow path."
        message = str(exit_row.get("message") or "").strip()
        if message:
            return message
        return "That way is blocked for now."

    def _movement_direction(self, head_raw: str, args: list[str]) -> str | None:
        if head_raw in DIRECTION_ALIASES:
            if head_raw in {"enter", "exit"} and args:
                # keep as movement for things like "enter house" and "exit house"
                return DIRECTION_ALIASES[head_raw]
            return DIRECTION_ALIASES[head_raw]
        if head_raw in {"go", "walk"} and args:
            return DIRECTION_ALIASES.get(args[0])
        return None

    def _robot_room(self, session: dict[str, object]) -> str:
        return str(self._object_locations(session).get("ROBOT") or "").strip().upper()

    def _robot_here(self, session: dict[str, object], room_id: str | None = None) -> bool:
        room_key = str(room_id or session.get("room") or START_ROOM).strip().upper() or START_ROOM
        return self._robot_room(session) == room_key

    def _robot_move_response(
        self,
        session: dict[str, object],
        direction: str,
    ) -> tuple[str, set[str], dict[str, str]]:
        room_id = self._robot_room(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if room_id not in ROOMS:
            return ('"I am only a stupid robot and cannot perform that command."', flags, object_locations)

        target = ""
        room = ROOMS.get(room_id)
        if room_id == "CAROU":
            if self._carousel_room_oriented(flags):
                if direction == "EXIT":
                    target = "PASS3"
                else:
                    for row in room.exits:
                        if str(row.get("direction") or "").strip().upper() == direction:
                            target = str(row.get("target") or "").strip().upper()
                            break
            elif direction in {"NORTH", "SOUTH", "EAST", "WEST", "NE", "NW", "SE", "SW", "EXIT"}:
                target = self._carousel_random_target(session)
        elif room_id == "MAGNE" and direction in MAGNET_FIXED_TARGETS:
            if self._magnet_room_disoriented(flags):
                target = self._magnet_random_target(session)
            else:
                target = MAGNET_FIXED_TARGETS[direction]
        else:
            for row in room.exits:
                if str(row.get("direction") or "").strip().upper() != direction:
                    continue
                kind = str(row.get("kind") or "")
                if kind == "room":
                    target = str(row.get("target") or "").strip().upper()
                    break
                if kind == "cexit" and self._condition_passes(session, str(row.get("condition") or ""), row):
                    target = str(row.get("target") or "").strip().upper()
                    break
                return ("The robot bumps into something invisible and gives up.", flags, object_locations)

        if target not in ROOMS:
            return ('"I am only a stupid robot and cannot perform that command."', flags, object_locations)

        object_locations["ROBOT"] = target
        return (f"The robot clanks off toward {room_name(target)}.", flags, object_locations)

    def _robot_take_sphere_response(
        self,
        session: dict[str, object],
    ) -> tuple[str, str, list[str], set[str], dict[str, str], bool]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if not self._robot_here(session, room_id):
            return ("The robot is not here.", room_id, inventory, flags, object_locations, False)
        if object_locations.get("SPHER") != room_id:
            return ("There is no sphere here for the robot to reach.", room_id, inventory, flags, object_locations, False)
        if "cage_solved" in flags:
            return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)
        object_locations["SPHER"] = "GONE"
        object_locations["ROBOT"] = "GONE"
        object_locations["RCAGE"] = room_id
        return (
            "As the robot reaches for the sphere, an iron cage falls from the ceiling. "
            "The robot attempts to fend it off, but is trapped below it. Alas, the robot short-circuits in his vain attempt to escape, "
            "and crushes the sphere beneath him as he falls to the floor.",
            room_id,
            inventory,
            flags,
            object_locations,
            False,
        )

    def _robot_raise_cage_response(
        self,
        session: dict[str, object],
    ) -> tuple[str, str, list[str], set[str], dict[str, str], bool]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if room_id != "CAGED" or not self._robot_here(session, "CAGED"):
            return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)
        flags.add("cage_solved")
        flags.discard("caged_trap")
        self._session_counters(session)["cage_gas_turns"] = 0
        object_locations["CAGE"] = "CAGER"
        object_locations["ROBOT"] = "CAGER"
        return (
            "The cage shakes and is hurled across the room.",
            "CAGER",
            inventory,
            flags,
            object_locations,
            False,
        )

    def _robot_command_response(
        self,
        session: dict[str, object],
        raw_command: str,
    ) -> tuple[str, str, list[str], set[str], dict[str, str], bool]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if not self._robot_here(session, room_id):
            return ("The robot is not here.", room_id, inventory, flags, object_locations, False)

        words = [part for part in self._clean_words(raw_command) if part]
        if not words:
            return ("Tell the robot to do what?", room_id, inventory, flags, object_locations, False)

        head = words[0]
        if head in DIRECTION_ALIASES or head in {"go", "walk"}:
            direction = self._movement_direction(head, words[1:])
            if direction is None:
                return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)
            reply, flags, object_locations = self._robot_move_response(session, direction)
            return (reply, room_id, inventory, flags, object_locations, False)

        if head in {"push", "press"}:
            target_text = " ".join(words[1:])
            target = self._resolve_object(session, target_text, head)
            if not target:
                return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)
            reply, flags, object_locations = self._push_or_press_response(session, target)
            button_names = {"SQBUT": "square button", "RNBUT": "round button", "TRBUT": "triangular button"}
            label = button_names.get(target, object_name(target))
            return (f"The robot obediently presses the {label}. {reply}", room_id, inventory, flags, object_locations, False)

        if head in {"take", "get"}:
            target_text = " ".join(words[1:])
            target = self._resolve_object(session, target_text, head)
            if target == "SPHER":
                return self._robot_take_sphere_response(session)
            return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)

        if head == "raise":
            target_text = " ".join(words[1:]).strip()
            if target_text and "cage" not in target_text and "bars" not in target_text:
                return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)
            return self._robot_raise_cage_response(session)

        return ('"I am only a stupid robot and cannot perform that command."', room_id, inventory, flags, object_locations, False)

    def _sphere_take_response(
        self,
        session: dict[str, object],
    ) -> tuple[str, str, list[str], set[str], dict[str, str], bool]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if object_locations.get("SPHER") != room_id:
            return ("You don't see any crystal sphere here.", room_id, inventory, flags, object_locations, False)
        if "cage_solved" in flags:
            inventory.append("SPHER")
            object_locations["SPHER"] = "INVENTORY"
            return (f"Taken: {object_name('SPHER')}.", room_id, inventory, flags, object_locations, False)
        if room_id != "CAGER":
            return ("You can't take the crystal sphere.", room_id, inventory, flags, object_locations, False)

        if not self._robot_here(session, room_id):
            object_locations["SPHER"] = "GONE"
            return (
                "As you reach for the sphere, an iron cage falls from the ceiling to entrap you. "
                "To make matters worse, poisonous gas starts coming into the room. "
                "You are stopped by a cloud of poisonous gas. zork: session ended. Send 'zork' to start again.",
                room_id,
                inventory,
                flags,
                object_locations,
                True,
            )

        flags.add("caged_trap")
        self._session_counters(session)["cage_gas_turns"] = 10
        object_locations["ROBOT"] = "CAGED"
        return (
            "As you reach for the sphere, an iron cage falls from the ceiling to entrap you. "
            "To make matters worse, poisonous gas starts coming into the room.",
            "CAGED",
            inventory,
            flags,
            object_locations,
            False,
        )

    def _move(self, session: dict[str, object], direction: str, now_unix: int) -> BotAppResult:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        room = ROOMS.get(room_id)
        if room is None:
            return BotAppResult(handled=True, reply_text="zork: lost in the map.", command_name=self.SPEC.name)
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        if room_id == "MTORC" and direction in {"UP", "CLIMB"} and "dome_rope_tied" in self._session_flags(session):
            return self._complete_transition(
                session,
                room_id="DOME",
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )

        if room_id == "CAROU":
            if self._carousel_room_oriented(flags):
                if direction == "EXIT":
                    return self._complete_transition(
                        session,
                        room_id="PASS3",
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                    )
                oriented_target = None
                for row in room.exits:
                    if str(row.get("direction") or "").strip().upper() == direction:
                        oriented_target = str(row.get("target") or "").strip().upper()
                        break
                if oriented_target in ROOMS:
                    return self._complete_transition(
                        session,
                        room_id=oriented_target,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                    )
            else:
                if direction in {"NORTH", "SOUTH", "EAST", "WEST", "NE", "NW", "SE", "SW", "EXIT"}:
                    return self._complete_transition_with_prefix(
                        session,
                        room_id=self._carousel_random_target(session),
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        prefix="Unfortunately, it is impossible to tell directions in here.",
                    )
        if room_id == "MAGNE":
            if direction in MAGNET_FIXED_TARGETS:
                if self._magnet_room_disoriented(flags):
                    return self._complete_transition_with_prefix(
                        session,
                        room_id=self._magnet_random_target(session),
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                        prefix="You cannot get your bearings...",
                    )
                return self._complete_transition(
                    session,
                    room_id=MAGNET_FIXED_TARGETS[direction],
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )

        if room_id == "LEDG4" and direction == "SOUTH" and self._safe_room_collapsed(flags):
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"Behind you, the walls of the safe room collapse into rubble. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        if room_id == "VAIR4" and direction == "EAST" and self._ledge4_collapsed(flags):
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"The ledge has collapsed and cannot be landed on. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        if room_id in GNOME_LEDGE_ROOMS and direction == "WEST":
            if "gnome_door_open" not in flags:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The volcano wall is unbroken there. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            return self._complete_transition_with_prefix(
                session,
                room_id="VLBOT",
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
                prefix="You squeeze through the little west door and slide down a narrow chimney.",
            )

        if room_id == "POG" and direction in {"UP", "NW", "WEST"}:
            if "rainbow_solid" not in flags:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The rainbow is not solid enough to support you. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            return self._complete_transition(
                session,
                room_id="RAINB",
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )

        if room_id == "ALISM" and direction in {"WEST", "NW", "DOWN"}:
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"There is a chasm too large to jump across. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        if room_id == "BARRE" and direction in {"LAUNC", "DOWN"}:
            self._sessions.pop(str(session.get("peer_id") or "").strip().lower(), None)
            return BotAppResult(
                handled=True,
                reply_text=self._compact(
                    "I didn't think you would REALLY try to go over the falls in a barrel. Some 450 feet below, you are met by unfriendly rocks and boulders. zork: session ended. Send 'zork' to start again."
                ),
                command_name=self.SPEC.name,
            )

        if "aboard_boat" in flags and object_locations.get("RBOAT") != room_id:
            flags.discard("aboard_boat")
        if "aboard_balloon" in flags and object_locations.get("BALLO") != room_id:
            flags.discard("aboard_balloon")
        if "aboard_bucket" in flags and object_locations.get("BUCKE") != room_id:
            flags.discard("aboard_bucket")
        if "aboard_bucket" in flags:
            if room_id in {"TWELL", "BWELL"} and direction in {"UP", "DOWN"}:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(
                        f"The bucket seems to respond only to the word 'well'. {self._room_summary(session, room_id)}"
                    ),
                    command_name=self.SPEC.name,
                )
            return BotAppResult(
                handled=True,
                reply_text=self._compact(
                    f"You'll have to climb out of the bucket first. {self._room_summary(session, room_id)}"
                ),
                command_name=self.SPEC.name,
            )

        exit_row = None
        for row in room.exits:
            if str(row.get("direction") or "").strip().upper() == direction:
                exit_row = row
                break

        if self._is_river_room(room_id):
            if "aboard_boat" not in flags:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"You are not in the boat. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if direction == "UP":
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The current is too strong to paddle upstream. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if room_id == "RIVR5" and direction == "DOWN":
                self._sessions.pop(str(session.get("peer_id") or "").strip().lower(), None)
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(
                        "The boat is sucked over the falls in a violence of water and noise. zork: session ended. Send 'zork' to start again."
                    ),
                    command_name=self.SPEC.name,
                )
            if exit_row is None:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"You can't go {direction.lower()} from the boat. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            kind = str(exit_row.get("kind") or "")
            if kind == "unknown" and direction == "EAST":
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The White Cliffs prevent your landing here. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if kind == "unknown":
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"That way is no use from the boat. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if kind == "nexit":
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"{self._blocked_exit_message(session, exit_row)} {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if kind == "cexit" and not self._condition_passes(session, str(exit_row.get("condition") or ""), exit_row):
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"{self._blocked_exit_message(session, exit_row)} {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            target = str(exit_row.get("target") or "").strip().upper()
            new_room = target if target in ROOMS else room_id
            object_locations["RBOAT"] = new_room
            return self._complete_transition(
                session,
                room_id=new_room,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )

        if direction == "LAUNC":
            if "aboard_balloon" in flags or object_locations.get("BALLO") == room_id or object_locations.get("DBALL") == room_id:
                if object_locations.get("DBALL") == room_id and "aboard_balloon" not in flags:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The balloon is broken. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if "aboard_balloon" not in flags:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You'll need to board the balloon first. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if object_locations.get("BALLO") != room_id:
                    flags.discard("aboard_balloon")
                    self._write_session_state(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                    )
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The balloon is not here anymore. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if self._balloon_tied_room(session) == room_id:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The balloon is fastened to the hook. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                burn_turns = self._balloon_burn_turns(session)
                if burn_turns <= 0 or "balloon_inflated" not in flags:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The balloon is not inflated. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if room_id == "VAIR4":
                    flags.discard("aboard_balloon")
                    flags.discard("balloon_inflated")
                    self._session_counters(session)["balloon_burn_turns"] = 0
                    object_locations["BALLO"] = "GONE"
                    object_locations["DBALL"] = "VLBOT"
                    self._sessions.pop(str(session.get("peer_id") or "").strip().lower(), None)
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(
                            "Your balloon has hit the rim of the volcano, ripping the cloth and causing you a 500 foot drop. "
                            "zork: session ended. Send 'zork' to start again."
                        ),
                        command_name=self.SPEC.name,
                    )
                if room_id in BALLOON_LAUNCH_MAP:
                    new_room = BALLOON_LAUNCH_MAP[room_id]
                elif room_id in BALLOON_ASCENT_MAP:
                    new_room = BALLOON_ASCENT_MAP[room_id]
                else:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You can't launch from here. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                object_locations["BALLO"] = new_room
                counters = self._session_counters(session)
                counters["balloon_burn_turns"] = max(0, burn_turns - 1)
                extra = ""
                if counters["balloon_burn_turns"] <= 0:
                    flags.discard("balloon_inflated")
                    extra = " The fire burns low and the cloth bag begins to sag."
                summary = self._room_summary_for_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                self._write_session_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The balloon ascends.{extra} {summary}"),
                    command_name=self.SPEC.name,
                )

            if "aboard_boat" not in flags:
                if object_locations.get("RBOAT") == room_id or "RBOAT" in inventory:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You'll need to board the boat first. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if object_locations.get("IBOAT") == room_id or "IBOAT" in inventory:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The boat is not yet inflated. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"You need a boat for that. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if object_locations.get("RBOAT") != room_id:
                flags.discard("aboard_boat")
                self._write_session_state(
                    session,
                    room_id=room_id,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The boat is not here anymore. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if exit_row is None:
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"You can't launch from here. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            kind = str(exit_row.get("kind") or "")
            if kind == "cexit" and not self._condition_passes(session, str(exit_row.get("condition") or ""), exit_row):
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"{self._blocked_exit_message(session, exit_row)} {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            if kind != "room":
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"You can't launch from here. {self._room_summary(session, room_id)}"),
                    command_name=self.SPEC.name,
                )
            target = str(exit_row.get("target") or "").strip().upper()
            new_room = target if target in ROOMS else room_id
            object_locations["RBOAT"] = new_room
            return self._complete_transition(
                session,
                room_id=new_room,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )

        if direction == "LAND":
            if "aboard_balloon" in flags or room_id in BALLOON_AIR_ROOMS:
                if "aboard_balloon" not in flags:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You'll need to board the balloon first. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if room_id in BALLOON_GROUND_ROOMS:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The balloon is already on the ground. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                if room_id == "VAIR4" and self._ledge4_collapsed(flags):
                    new_room = BALLOON_DESCENT_MAP[room_id]
                    move_text = "The balloon descends."
                elif room_id in BALLOON_LANDING_MAP:
                    new_room = BALLOON_LANDING_MAP[room_id]
                    move_text = "The balloon lands."
                elif room_id in BALLOON_DESCENT_MAP:
                    new_room = BALLOON_DESCENT_MAP[room_id]
                    move_text = "The balloon descends."
                else:
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You can't land from here. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                burn_turns = self._balloon_burn_turns(session)
                if new_room == "VLBOT" and burn_turns <= 0:
                    flags.discard("aboard_balloon")
                    flags.discard("balloon_inflated")
                    self._session_counters(session)["balloon_burn_turns"] = 0
                    object_locations["BALLO"] = "GONE"
                    object_locations["DBALL"] = "VLBOT"
                    summary = self._room_summary_for_state(
                        session,
                        room_id="VLBOT",
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                    )
                    self._write_session_state(
                        session,
                        room_id="VLBOT",
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                        now_unix=now_unix,
                    )
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"You have landed, but the balloon did not survive. {summary}"),
                        command_name=self.SPEC.name,
                    )
                object_locations["BALLO"] = new_room
                summary = self._room_summary_for_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                self._write_session_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"{move_text} {summary}"),
                    command_name=self.SPEC.name,
                )

        if "aboard_balloon" in flags:
            if room_id == "VAIR2" and direction == "WEST" and exit_row is not None:
                new_room = "LEDG2"
                object_locations["BALLO"] = new_room
                summary = self._room_summary_for_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                self._write_session_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The balloon lands. {summary}"),
                    command_name=self.SPEC.name,
                )
            if room_id == "VAIR4" and direction == "EAST" and exit_row is not None:
                if self._ledge4_collapsed(flags):
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(f"The ledge has collapsed and cannot be landed on. {self._room_summary(session, room_id)}"),
                        command_name=self.SPEC.name,
                    )
                new_room = "LEDG4"
                object_locations["BALLO"] = new_room
                summary = self._room_summary_for_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                self._write_session_state(
                    session,
                    room_id=new_room,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(f"The balloon lands. {summary}"),
                    command_name=self.SPEC.name,
                )
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"I'm afraid you can't control the balloon in this way. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        if "aboard_boat" in flags and self._has_launch_exit(room_id):
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"You'll have to disembark first. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        if exit_row is None:
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"You can't go {direction.lower()}. {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )
        kind = str(exit_row.get("kind") or "")
        if kind == "room":
            target = str(exit_row.get("target") or "").strip().upper()
            new_room = target if target in ROOMS else room_id
            return self._complete_transition(
                session,
                room_id=new_room,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )
        if kind == "cexit" and self._condition_passes(session, str(exit_row.get("condition") or ""), exit_row):
            target = str(exit_row.get("target") or "").strip().upper()
            if target in ROOMS:
                return self._complete_transition(
                    session,
                    room_id=target,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                    now_unix=now_unix,
                )
        return BotAppResult(
            handled=True,
            reply_text=self._compact(f"{self._blocked_exit_message(session, exit_row)} {self._room_summary(session, room_id)}"),
            command_name=self.SPEC.name,
        )

    def _inventory_text(self, session: dict[str, object]) -> str:
        inventory = self._session_inventory(session)
        if not inventory:
            return "inventory: empty"
        labels: list[str] = []
        sword_glow = self._sword_glow_level(session)
        for code in inventory:
            label = object_name(code)
            if self._object_is_lit(session, code):
                label += " (lit)"
            elif code in {"CANDL", "TORCH"}:
                label += " (dark)"
            if code == "SWORD":
                if sword_glow >= 2:
                    label += " (bright blue glow)"
                elif sword_glow == 1:
                    label += " (faint blue glow)"
            labels.append(label)
        return self._compact(f"inventory: {', '.join(labels)}")

    def _describe_object(self, session: dict[str, object], code: str) -> str:
        code_key = str(code or "").strip().upper()
        item = OBJECTS.get(code_key)
        if item is None:
            return "You see nothing special."
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key == "MAILB":
            state = "open" if "mailbox_open" in flags else "closed"
            if object_locations.get("ADVER") == "MAILB":
                return self._compact(f"A small mailbox. It is {state}. A leaflet is inside." if state == "open" else f"A small mailbox. It is {state}.")
            return self._compact(f"A small mailbox. It is {state}.")
        if code_key == "FLASK":
            return "A stoppered glass flask marked with a skull and crossbones."
        if code_key == "POOL":
            return (
                "The depression is dry now, with only a nasty stain left where the sewage used to be."
                if "pool_evaporated" in flags
                else "A disgusting pool of sewage fed by the leak above."
            )
        if code_key == "SAFFR":
            return "A tin of rare spices."
        if code_key == "BUCKE":
            return "A wooden bucket, large enough to ride in if you are feeling imprudent."
        if code_key == "ECAKE":
            return "A piece of cake bearing the words 'Eat Me'."
        if code_key == "ORICE":
            return "A piece of cake with orange icing. Tiny letters are written on it."
        if code_key == "RDICE":
            return "A piece of cake with red icing. Tiny letters are written on it."
        if code_key == "BLICE":
            return "A piece of cake with blue icing. Tiny letters are written on it."
        if code_key == "POSTS":
            return "Four huge wooden posts support what, at this scale, looks suspiciously like a gigantic table."
        if code_key == "DAM":
            return "Flood Control Dam #3 looms here like a slab of overconfident engineering."
        if code_key == "ICE":
            return (
                "The remains of the glacier have melted away, leaving an open passage west."
                if "glacier_melted" in flags
                else "A massive glacier fills the western half of the room."
            )
        if code_key in {"REFL1", "REFL2"}:
            return "The mirror is broken into many pieces." if "mirror_broken" in flags else "There is an ugly person staring at you."
        if code_key == "MACHI":
            return (
                "A hulking machine with its lid open. It looks ready to digest unfortunate objects."
                if "machine_open" in flags
                else "A hulking machine with a shut lid and a sturdy switch."
            )
        if code_key == "MSWIT":
            return "A sturdy switch on the side of the machine. A screwdriver might persuade it."
        if code_key == "SAFE":
            if self._safe_room_collapsed(flags):
                return "The safe room has collapsed into rubble."
            return (
                "A rusty safe with its door blown off."
                if "safe_blown" in flags
                else "A rusty old box imbedded in the wall. It looks jammed, and a slot has been chipped in front."
            )
        if code_key == "TCASE":
            contents = self._container_contents(session, "TCASE")
            if not contents:
                return "A trophy case. At the moment it is empty."
            labels = ", ".join(object_name(value) for value in contents)
            return self._compact(f"A trophy case. It currently holds: {labels}.")
        if code_key == "SSLOT":
            return "The chipped-out slot in the front of the box." if "safe_blown" not in flags else "The blasted opening in the front of the safe."
        if code_key == "FUSE":
            if "fuse_lit" in flags:
                return "A fuse burning down toward very poor life choices."
            return "A fuse threaded for use with the brick."
        if code_key == "GATES":
            return (
                "A black gateway stands open, no longer crowded by evil spirits."
                if "lld_open" in flags
                else "A black gateway bars the way, choked with evil spirits."
            )
        if code_key == "BOLT":
            return "A large metal bolt on the control panel. It looks as though a wrench might persuade it."
        if code_key == "BUBBL":
            return "A small green bubble above the bolt. It is glowing." if "gate_enabled" in flags else "A small green bubble above the bolt. It is dark."
        if code_key in {"SQBUT", "RNBUT", "TRBUT"}:
            button_names = {"SQBUT": "square", "RNBUT": "round", "TRBUT": "triangular"}
            return f"A {button_names.get(code_key, 'mysterious')} button mounted on the machine-room panel."
        if code_key in {"BLBUT", "BRBUT", "RBUTT", "YBUTT"}:
            button_names = {"BLBUT": "blue", "BRBUT": "brown", "RBUTT": "red", "YBUTT": "yellow"}
            return f"A {button_names.get(code_key, 'mysterious')} button mounted on the panel."
        if code_key == "LEAK":
            return (
                "A burst leak in the east wall sprays water across the room."
                if "maintenance_leak_active" in flags
                else "A suspicious section of pipe in the east wall. At the moment it is dry."
            )
        if code_key == "BAT":
            return "A large vampire bat clings to the ceiling, glaring at you with weirdly personal disapproval."
        if code_key == "GNOME":
            if "gnome_door_open" in flags:
                return "A nervous volcano gnome checks his watch and admires the little west door he just arranged for you."
            return "A nervous volcano gnome glances at his watch and looks as though he expects to be paid promptly."
        if code_key == "THIEF":
            return self._compact(
                "There is a suspicious-looking individual, holding a bag and a vicious-looking stiletto, leaning against one wall."
                if "thief_defeated" not in flags
                else "There is a suspicious-looking individual lying unconscious on the ground. His bag and stiletto have spilled their contents."
            )
        if code_key == "GHOST":
            return (
                "The spirits are gone. The gateway now lies open."
                if "lld_open" in flags
                else "A pack of evil spirits hover near the gate, radiating bureaucratic malice."
            )
        if code_key == "TORCH":
            if "torch_burned_out" in flags:
                return "A burned out ivory torch. It has no more fire left to give."
            return "An ivory torch, blazing steadily." if self._object_is_lit(session, "TORCH") else "An ivory torch. It is no longer burning."
        if code_key == "CANDL":
            return "A pair of candles. They are burning." if self._object_is_lit(session, "CANDL") else "A pair of candles. They have gone out."
        if code_key == "BALLO":
            fuel_code = self._balloon_fuel_code(session)
            fuel_text = ""
            if fuel_code:
                if self._balloon_inflated(session):
                    fuel_text = f" A {object_name(fuel_code)} burns in the receptacle, keeping the bag full of hot air."
                else:
                    fuel_text = f" A {object_name(fuel_code)} rests in the receptacle."
            tie_text = " The wire is fastened to a hook in the rock." if self._balloon_tied_room(session) == room_id else ""
            if self._balloon_inflated(session):
                return self._compact(f"A large balloon with an inflated cloth bag above a wicker basket.{fuel_text}{tie_text}")
            return self._compact(f"A large balloon basket with its cloth bag draped over the sides.{fuel_text}{tie_text}")
        if code_key == "DBALL":
            return "A shattered balloon. It has very much failed at being a balloon."
        if code_key == "RECEP":
            fuel_code = self._balloon_fuel_code(session)
            if fuel_code and self._balloon_inflated(session):
                return self._compact(f"A metal receptacle inside the basket. A {object_name(fuel_code)} is burning in it.")
            if fuel_code:
                return self._compact(f"A metal receptacle inside the basket. It currently holds {object_name(fuel_code)}.")
            return "A metal receptacle mounted inside the basket. It appears to be the balloon's burner."
        if code_key == "BROPE":
            if self._balloon_tied_room(session) == room_id:
                return "A braided wire running from the basket to the hook in the rock."
            return "A braided wire attached to the outside of the balloon basket."
        if code_key in {"HOOK1", "HOOK2"}:
            if self._balloon_tied_room(session) == room_id:
                return "A small hook attached to the rock. The balloon's wire is fastened to it."
            return "A small hook attached to the rock."
        if code_key == "BUOY":
            return "A red buoy. It is open." if "buoy_open" in flags else "A red buoy, probably a warning. It looks like it can be opened."
        if code_key == "LABEL":
            return "A tan label attached to the magic boat."
        if code_key in {"WIND1", "WIND2"}:
            return self._compact("A small kitchen window. It is open." if "kitchen_window_open" in flags else "A small kitchen window, slightly ajar.")
        if code_key in {"DOOR", "TDOOR"}:
            return self._compact("A trap door. It is open." if "trap_door_open" in flags else "A trap door. It is closed.")
        if code_key in {"GRAT1", "GRAT2"}:
            if "grating_open" in flags:
                return "A metal grating stands open."
            if "grating_unlocked" in flags:
                return "A metal grating. It is unlocked but closed."
            return "A metal grating secured with a nasty lock."
        if code_key == "RAILI":
            return "A sturdy wooden railing circles the edge of the dome."
        if code_key == "RUG":
            return self._compact(
                "The rug is shoved aside, exposing the trap door."
                if "rug_moved" in flags
                else "A large oriental rug covers the center of the room."
            )
        if code_key == "LEAVE":
            return self._compact(
                "A pile of leaves has been disturbed, revealing the grating beneath."
                if "leaves_moved" in flags
                else "A pile of leaves rests on the ground."
            )
        if code_key == "TROLL":
            return self._compact(
                "An unconscious troll lies sprawled here."
                if "troll_defeated" in flags
                else "A nasty-looking troll brandishing a bloody axe blocks your way."
            )
        if code_key == "CYCLO":
            return self._compact(
                "The cyclops has fled, leaving the staircase clear."
                if "cyclops_gone" in flags
                else "A huge cyclops blocks the staircase and eyes you like a suspicious appetizer."
            )
        if code_key == "RAINB":
            return self._compact(
                "A solid rainbow spans the falls. You could walk on it."
                if "rainbow_solid" in flags
                else "A beautiful rainbow arcs over the falls. It does not look terribly load-bearing."
            )
        if code_key == "SDOOR":
            return self._compact(
                "The great stone door stands open."
                if "riddle_solved" in flags
                else "A great stone door bars the east wall. The riddle above it looks annoyingly serious."
            )
        if code_key == "ROPE" and room_id == "DOME" and "dome_rope_tied" in flags:
            return "The rope is tied to the railing and drops into the room below."
        if code_key == "LAMP":
            return self._compact("A brass lantern. It is glowing warmly." if "lamp_lit" in flags else "A brass lantern. It is switched off.")
        if code_key == "LABEL":
            return "A tan label attached to the magic boat. There is writing on it."
        if code_key == "SWORD":
            glow_text = self._sword_glow_text(session, room_id)
            if glow_text:
                return self._compact(f"An elvish sword of great antiquity. {glow_text}")
        if item.read_desc:
            return self._compact(item.read_desc)
        if item.detail_desc:
            return self._compact(item.detail_desc)
        if item.short_desc:
            return self._compact(item.short_desc)
        return self._compact(f"You see {object_name(code_key)}.")

    def _read_object(self, session: dict[str, object], code: str, viewer_code: str | None = None) -> str:
        code_key = str(code or "").strip().upper()
        viewer_key = str(viewer_code or "").strip().upper()
        item = OBJECTS.get(code_key)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if item is None:
            return "There's nothing readable there."
        if code_key == "ECAKE":
            return "The icing spells out 'Eat Me'."
        if code_key in {"ORICE", "RDICE", "BLICE"}:
            if viewer_key == "BOTTL":
                return self._compact("The letters appear larger, but still are too small to be read.")
            if viewer_key == "FLASK":
                meanings = {"RDICE": "Evaporate", "ORICE": "Explode", "BLICE": "Enlarge"}
                return self._compact(f"The icing, now visible, says '{meanings.get(code_key, 'Enlarge')}'.")
            if viewer_key:
                return "You can't see through that!"
            if room_id.startswith("ALI"):
                return self._compact("The only writing legible is a capital E. The rest is too small to be clearly visible.")
        if item.read_desc:
            return self._compact(item.read_desc)
        if code_key == "LABEL":
            return self._compact(
                "!!!! FROBOZZ MAGIC BOAT COMPANY !!!! Instructions: Board to get in, Disembark to get out, Launch to enter the water, Land to reach shore. Warranty basically imaginary."
            )
        if code_key == "WDOOR":
            return self._compact("The engravings translate to 'This space intentionally left blank'.")
        return f"There's nothing written on the {object_name(code_key)}."

    def _eat_response(
        self,
        session: dict[str, object],
        code: str,
    ) -> tuple[str, str | None, list[str], set[str], dict[str, str], bool]:
        code_key = str(code or "").strip().upper()
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        item = OBJECTS.get(code_key)
        if item is None:
            return ("That doesn't look edible.", room_id, inventory, flags, object_locations, False)
        if code_key == "ECAKE" and room_id == "ALICE" and self._is_accessible(session, "ECAKE"):
            inventory, object_locations = self._consume_accessible_object(session, "ECAKE", inventory, object_locations)
            object_locations = self._shift_room_contents(object_locations, "ALICE", "ALISM", exclude={"ATABL"})
            return ("Suddenly, the room appears to have become very large.", "ALISM", inventory, flags, object_locations, False)
        if code_key == "BLICE" and room_id.startswith("ALI") and self._is_accessible(session, "BLICE"):
            inventory, object_locations = self._consume_accessible_object(session, "BLICE", inventory, object_locations)
            if room_id == "ALISM":
                object_locations = self._shift_room_contents(object_locations, "ALISM", "ALICE", exclude={"POSTS"})
                return ("The room around you seems to be getting smaller.", "ALICE", inventory, flags, object_locations, False)
            return (
                "The room seems to have become too small to hold you. The walls are not as compressible as your body. zork: session ended. Send 'zork' to start again.",
                room_id,
                inventory,
                flags,
                object_locations,
                True,
            )
        if code_key == "ORICE" and room_id.startswith("ALI") and self._is_accessible(session, "ORICE"):
            inventory, object_locations = self._consume_accessible_object(session, "ORICE", inventory, object_locations)
            return (
                "The cake detonates into sticky orange rubble and you are blasted to smithereens. zork: session ended. Send 'zork' to start again.",
                room_id,
                inventory,
                flags,
                object_locations,
                True,
            )
        if code_key == "RDICE" and self._is_accessible(session, "RDICE"):
            inventory, object_locations = self._consume_accessible_object(session, "RDICE", inventory, object_locations)
            return ("You eat the red cake. Nothing obvious happens.", room_id, inventory, flags, object_locations, False)
        if "FOODBIT" not in item.flags:
            return ("That doesn't look edible.", room_id, inventory, flags, object_locations, False)
        if not self._is_accessible(session, code_key):
            return (f"You don't have the {object_name(code_key)}.", room_id, inventory, flags, object_locations, False)
        inventory, object_locations = self._consume_accessible_object(session, code_key, inventory, object_locations)
        return ("Thank you very much. It really hit the spot.", room_id, inventory, flags, object_locations, False)

    def _open_close_response(self, session: dict[str, object], code: str, action: str) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key == "MAILB":
            if action == "open":
                if "mailbox_open" in flags:
                    return ("It's already open.", flags, object_locations)
                flags.add("mailbox_open")
                if object_locations.get("ADVER") == "MAILB":
                    return ("Opening the mailbox reveals a small leaflet.", flags, object_locations)
                return ("The mailbox opens.", flags, object_locations)
            if "mailbox_open" not in flags:
                return ("It's already closed.", flags, object_locations)
            flags.discard("mailbox_open")
            return ("The mailbox closes.", flags, object_locations)
        if code_key == "BUOY":
            if action == "open":
                if "buoy_open" in flags:
                    return ("The buoy is already open.", flags, object_locations)
                flags.add("buoy_open")
                if object_locations.get("EMERA") == "BUOY":
                    return ("The buoy opens, revealing a large emerald.", flags, object_locations)
                return ("The buoy opens.", flags, object_locations)
            if "buoy_open" not in flags:
                return ("The buoy is already closed.", flags, object_locations)
            flags.discard("buoy_open")
            return ("The buoy closes again.", flags, object_locations)
        if code_key in {"WIND1", "WIND2"}:
            if action == "open":
                if "kitchen_window_open" in flags:
                    return ("The window is already open.", flags, object_locations)
                flags.add("kitchen_window_open")
                return ("With great effort, you open the window far enough to allow entry.", flags, object_locations)
            if "kitchen_window_open" not in flags:
                return ("The window is already only slightly ajar.", flags, object_locations)
            flags.discard("kitchen_window_open")
            return ("The window closes more easily than it opened.", flags, object_locations)
        if code_key in {"DOOR", "TDOOR"}:
            if room_id == "LROOM" and "rug_moved" not in flags and "trap_door_open" not in flags:
                return ("You need to move the rug first.", flags, object_locations)
            if action == "open":
                if "trap_door_open" in flags:
                    return ("It's open.", flags, object_locations)
                flags.add("trap_door_open")
                return ("The trap door reluctantly opens to reveal a rickety staircase descending into darkness.", flags, object_locations)
            if "trap_door_open" not in flags:
                return ("It's closed.", flags, object_locations)
            flags.discard("trap_door_open")
            return ("The trap door swings shut and closes.", flags, object_locations)
        if code_key in {"GRAT1", "GRAT2"}:
            if action == "open":
                if "grating_open" in flags:
                    return ("It's already open.", flags, object_locations)
                if "grating_unlocked" not in flags:
                    if "KEYS" in set(self._session_inventory(session)):
                        flags.add("grating_unlocked")
                    else:
                        return ("The grating is locked.", flags, object_locations)
                flags.add("grating_open")
                return ("The grating opens.", flags, object_locations)
            if "grating_open" not in flags:
                return ("It's already closed.", flags, object_locations)
            flags.discard("grating_open")
            return ("The grating is closed.", flags, object_locations)
        if code_key == "MACHI":
            if action == "open":
                if "machine_open" in flags:
                    return ("The lid is already open.", flags, object_locations)
                flags.add("machine_open")
                return ("The lid opens.", flags, object_locations)
            if "machine_open" not in flags:
                return ("The lid is already closed.", flags, object_locations)
            flags.discard("machine_open")
            return ("The lid closes.", flags, object_locations)
        if code_key == "SAFE":
            if action == "open":
                if "safe_blown" in flags:
                    return ("The box has no door!", flags, object_locations)
                return ("The box is rusted and will not open.", flags, object_locations)
            if "safe_blown" in flags:
                return ("The box has no door!", flags, object_locations)
            return ("The box is not open, chomper!", flags, object_locations)
        if code_key == "TCASE":
            return ("The trophy case is already open.", flags, object_locations)
        if code_key in {"FDOOR", "WDOOR", "SDOOR"}:
            if code_key == "SDOOR" and room_id == "RIDDL":
                if "riddle_solved" in flags:
                    return ("The stone door is already open.", flags, object_locations)
                return ("The stone door will not budge until the riddle is answered.", flags, object_locations)
            return ("The door cannot be opened.", flags, object_locations)
        return (f"You can't {action} the {object_name(code_key)}.", flags, object_locations)

    def _take_response(self, session: dict[str, object], code: str) -> tuple[str, list[str], dict[str, str], set[str]]:
        code_key = str(code or "").strip().upper()
        item = OBJECTS.get(code_key)
        inventory = self._session_inventory(session)
        object_locations = self._object_locations(session)
        flags = self._session_flags(session)
        counters = self._session_counters(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if item is None:
            return ("You can't take that.", inventory, object_locations, flags)
        if code_key in inventory:
            return (f"You already have the {object_name(code_key)}.", inventory, object_locations, flags)
        if not self._is_accessible(session, code_key):
            return (f"You don't see any {object_name(code_key)} here.", inventory, object_locations, flags)
        if code_key == "ROPE" and room_id == "DOME" and "dome_rope_tied" in flags:
            return ("The rope is tied to the railing.", inventory, object_locations, flags)
        if code_key == "RBOAT" and "aboard_boat" in flags and object_locations.get("RBOAT") == room_id:
            return ("You are already in the boat.", inventory, object_locations, flags)
        if code_key == "SPHER":
            if "cage_solved" not in flags:
                return ("As you reach for the sphere, something very unfortunate happens. Perhaps the robot should be here first.", inventory, object_locations, flags)
            inventory.append(code_key)
            object_locations[code_key] = "INVENTORY"
            return (f"Taken: {object_name(code_key)}.", inventory, object_locations, flags)
        if code_key == "BODIE":
            return ("A force keeps you from taking the bodies.", inventory, object_locations, flags)
        if code_key == "GUNK":
            object_locations.pop("GUNK", None)
            return (
                "The slag crumbles into dust at your touch. It must not have been very valuable.",
                inventory,
                object_locations,
                flags,
            )
        if code_key == "RUG":
            return ("The rug is too heavy to take.", inventory, object_locations, flags)
        if code_key == "LEAVE":
            flags.add("leaves_moved")
        if code_key == "WATER":
            return ("The water is already in the bottle.", inventory, object_locations, flags)
        if str(object_locations.get(code_key) or "").strip().upper() == "RECEP":
            flags.discard("balloon_inflated")
            counters["balloon_burn_turns"] = 0
        if code_key == "AXE" and object_locations.get("AXE") == "TROLL" and "troll_defeated" in flags:
            object_locations["AXE"] = room_id
        if "TAKEBIT" not in item.flags and code_key not in {"AXE", "LEAVE"}:
            return (f"You can't take the {object_name(code_key)}.", inventory, object_locations, flags)
        inventory.append(code_key)
        object_locations[code_key] = "INVENTORY"
        if code_key == "ADVER" and object_locations.get("ADVER") == "MAILB":
            object_locations["ADVER"] = "INVENTORY"
        return (f"Taken: {object_name(code_key)}.", inventory, object_locations, flags)

    def _drop_response(self, session: dict[str, object], code: str) -> tuple[str, list[str], dict[str, str], set[str]]:
        code_key = str(code or "").strip().upper()
        inventory = self._session_inventory(session)
        object_locations = self._object_locations(session)
        flags = self._session_flags(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key not in inventory:
            return (f"You aren't carrying the {object_name(code_key)}.", inventory, object_locations, flags)
        if code_key == "RBOAT" and "aboard_boat" in flags:
            return ("You would have to leave the boat first.", inventory, object_locations, flags)
        inventory = [value for value in inventory if value != code_key]
        if code_key == "ROPE" and room_id == "DOME" and "dome_rope_tied" not in flags:
            object_locations[code_key] = "MTORC"
            return ("The rope drops gently to the floor below.", inventory, object_locations, flags)
        object_locations[code_key] = room_id
        if code_key == "LAMP":
            flags.discard("lamp_lit")
        return (f"Dropped: {object_name(code_key)}.", inventory, object_locations, flags)

    def _move_or_lift_response(self, session: dict[str, object], code: str) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key == "RUG" and room_id == "LROOM":
            if "rug_moved" in flags:
                return ("The rug has already been shoved aside.", flags, object_locations)
            flags.add("rug_moved")
            return ("With a great effort, the rug is moved aside. Under it is a closed trap door.", flags, object_locations)
        if code_key == "LEAVE" and room_id == "CLEAR":
            if "leaves_moved" in flags:
                return ("The leaves have already been disturbed, and the grating is visible.", flags, object_locations)
            flags.add("leaves_moved")
            object_locations.setdefault("GRAT1", "CLEAR")
            return ("A grating appears on the ground beneath the leaves.", flags, object_locations)
        return (f"Moving the {object_name(code_key)} accomplishes nothing.", flags, object_locations)

    def _raise_lower_response(
        self,
        session: dict[str, object],
        action: str,
        code: str,
    ) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        action_key = str(action or "").strip().lower()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key == "CAGE":
            if room_id != "CAGED":
                return ("There is no cage here to raise.", flags, object_locations)
            return ("The iron cage is not exactly built for your leverage.", flags, object_locations)

        if code_key != "TBASK":
            return (f"You can't {action_key} the {object_name(code_key)}.", flags, object_locations)
        if room_id not in {"TSHAF", "BSHAF"}:
            return (f"There is no basket here to {action_key}.", flags, object_locations)

        basket_room = str(object_locations.get("TBASK") or room_id).strip().upper() or room_id
        if action_key == "raise":
            if basket_room == "TSHAF":
                return ("The basket is already at the top of the shaft.", flags, object_locations)
            object_locations["TBASK"] = "TSHAF"
            object_locations["FBASK"] = "GONE"
            return ("The basket is raised to the top of the shaft.", flags, object_locations)

        if basket_room == "BSHAF":
            return ("The basket is already at the bottom of the shaft.", flags, object_locations)
        object_locations["TBASK"] = "BSHAF"
        object_locations["FBASK"] = "GONE"
        return ("The basket is lowered to the bottom of the shaft.", flags, object_locations)

    def _dig_response(self, session: dict[str, object], tool_code: str | None) -> tuple[str, set[str], dict[str, str], bool]:
        tool_key = str(tool_code or "SHOVE").strip().upper() or "SHOVE"
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if tool_key != "SHOVE" or "SHOVE" not in set(self._session_inventory(session)):
            return ("Digging requires a shovel.", flags, object_locations, False)

        counters = self._session_counters(session)
        if room_id == "BEACH":
            count = int(counters.get("beach_digs") or 0) + 1
            counters["beach_digs"] = count
            if count > 4:
                return ("The hole collapses, smothering you. zork: session ended. Send 'zork' to start again.", flags, object_locations, True)
            if count == 4:
                flags.add("beach_statue_found")
                object_locations["STATU"] = "BEACH"
                return ("You can see a small statue here in the sand.", flags, object_locations, False)
            progress = (
                "You seem to be digging a hole here.",
                "The hole is getting deeper, but that's about it.",
                "You are surrounded by a wall of sand on all sides.",
            )
            return (progress[count - 1], flags, object_locations, False)

        if room_id == "TCAVE":
            if str(object_locations.get("GUANO") or "").strip().upper() != room_id:
                return ("There's nothing to dig into here.", flags, object_locations, False)
            count = int(counters.get("tcave_digs") or 0) + 1
            counters["tcave_digs"] = count
            if count > 3:
                return ("This is getting you nowhere.", flags, object_locations, False)
            progress = (
                "You are digging into a pile of bat guano.",
                "You seem to be getting knee deep in guano.",
                "You are covered with bat turds, cretin.",
            )
            return (progress[count - 1], flags, object_locations, False)

        return ("There's nothing to dig into here.", flags, object_locations, False)

    def _lamp_response(self, session: dict[str, object], action: str) -> tuple[str, set[str]]:
        flags = self._session_flags(session)
        inventory = set(self._session_inventory(session))
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        object_locations = self._object_locations(session)
        lamp_here = object_locations.get("LAMP") == room_id
        if "LAMP" not in inventory and not lamp_here:
            return ("You have no lamp handy.", flags)
        if action == "on":
            if "lamp_lit" in flags:
                return ("The lamp is already on.", flags)
            flags.add("lamp_lit")
            return ("The brass lantern glows to life.", flags)
        if "lamp_lit" not in flags:
            return ("The lamp is already off.", flags)
        flags.discard("lamp_lit")
        return ("The lantern goes dark.", flags)

    def _attack_response(self, session: dict[str, object], target_code: str | None = None) -> tuple[str, set[str], dict[str, str], bool]:
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        inventory = set(self._session_inventory(session))
        target_key = str(target_code or "").strip().upper()
        visible = set(self._visible_top_level_objects(session, room_id))
        if not target_key:
            for candidate in ("THIEF", "TROLL", "CYCLO", "GHOST"):
                if candidate in visible:
                    target_key = candidate
                    break
        if target_key == "GHOST":
            if "GHOST" not in visible:
                return ("There are no spirits here to attack.", flags, object_locations, False)
            return ("You seem unable to affect these spirits.", flags, object_locations, False)
        if target_key == "BODIE":
            if "BODIE" not in visible:
                return ("There are no bodies here to attack.", flags, object_locations, False)
            return (self._guardian_of_the_dungeon_death(), flags, object_locations, True)
        if target_key == "THIEF":
            if "THIEF" not in visible:
                return ("There's no thief here to attack.", flags, object_locations, False)
            if "thief_defeated" in flags:
                return ("The thief is already unconscious.", flags, object_locations, False)
            if not inventory.intersection(WEAPON_CODES):
                return ("The thief eyes you coldly and keeps one hand on his stiletto.", flags, object_locations, False)
            flags.add("thief_defeated")
            for code, location in list(object_locations.items()):
                if str(location or "").strip().upper() != "THIEF":
                    continue
                object_locations[code] = room_id
            object_locations["THIEF"] = room_id
            return (
                "The thief collapses in a heap. As his grip slackens, the contents of his bag spill onto the floor.",
                flags,
                object_locations,
                False,
            )
        if target_key == "CYCLO":
            if room_id != "CYCLO" or "CYCLO" not in visible:
                return ("There's no cyclops here to attack.", flags, object_locations, False)
            return ("The cyclops looks less injured than irritated. This seems unpromising.", flags, object_locations, False)
        if room_id != "MTROL" or "TROLL" not in visible:
            return ("There's nothing here looking for a fight.", flags, object_locations, False)
        if "troll_defeated" in flags:
            return ("The troll is already down.", flags, object_locations, False)
        if not inventory.intersection(WEAPON_CODES - {"STILL"}):
            return ("The troll fends you off with a menacing gesture.", flags, object_locations, False)
        flags.add("troll_defeated")
        object_locations["AXE"] = room_id
        return ("The troll collapses in a heap, dropping his bloody axe. The passages are open.", flags, object_locations, False)

    def _push_or_press_response(self, session: dict[str, object], code: str) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)

        if code_key == "SQBUT":
            if "carousel_zoom" in flags:
                return ("Nothing seems to happen.", flags, object_locations)
            flags.add("carousel_zoom")
            return ("The whirring increases in intensity slightly.", flags, object_locations)
        if code_key == "RNBUT":
            if "carousel_zoom" not in flags:
                return ("Nothing seems to happen.", flags, object_locations)
            flags.discard("carousel_zoom")
            return ("The whirring decreases in intensity slightly.", flags, object_locations)
        if code_key == "TRBUT":
            if "carousel_flip" in flags:
                flags.discard("carousel_flip")
            else:
                flags.add("carousel_flip")
            if str(object_locations.get("IRBOX") or "").strip().upper() == "CAROU":
                return ("A dull thump is heard in the distance.", flags, object_locations)
            return ("Nothing obvious happens.", flags, object_locations)
        if code_key == "YBUTT":
            flags.add("gate_enabled")
            return ("Click. The small green bubble glows.", flags, object_locations)
        if code_key == "BRBUT":
            flags.discard("gate_enabled")
            return ("Click. The green bubble goes dark.", flags, object_locations)
        if code_key == "RBUTT":
            if "maintenance_lights_on" in flags:
                flags.discard("maintenance_lights_on")
                return ("The lights within the room shut off.", flags, object_locations)
            flags.add("maintenance_lights_on")
            return ("The lights within the room come on.", flags, object_locations)
        if code_key == "BLBUT":
            if "maintenance_leak_active" in flags:
                return ("The blue button appears to be jammed.", flags, object_locations)
            flags.add("maintenance_leak_active")
            return (
                "There is a rumbling sound and a stream of water bursts from the east wall of the room.",
                flags,
                object_locations,
            )
        return (f"Pushing the {object_name(code_key)} accomplishes nothing.", flags, object_locations)

    def _turn_response(
        self,
        session: dict[str, object],
        code: str,
        tool_code: str | None,
    ) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        tool_key = str(tool_code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)

        if code_key == "BOLT":
            if tool_key and tool_key != "WRENC":
                return (f"The bolt won't turn using the {object_name(tool_key)}.", flags, object_locations)
            if tool_key != "WRENC":
                return ("The bolt won't turn with your best effort.", flags, object_locations)
            if "gate_enabled" not in flags:
                return ("The bolt won't turn with your best effort.", flags, object_locations)
            if "low_tide" in flags:
                flags.discard("low_tide")
                return ("The sluice gates close and water starts to collect behind the dam.", flags, object_locations)
            flags.add("low_tide")
            return ("The sluice gates open and water pours through the dam.", flags, object_locations)

        if code_key == "MSWIT":
            if tool_key and tool_key != "SCREW":
                return (f"It seems that a {object_name(tool_key)} won't do.", flags, object_locations)
            if tool_key != "SCREW":
                return ("The switch resists your fingers. A screwdriver looks more convincing.", flags, object_locations)
            if "machine_open" in flags:
                return ("The machine doesn't seem to want to do anything.", flags, object_locations)
            contents = [item_code for item_code, location in object_locations.items() if location == "MACHINE" and item_code not in {"MACHI", "MSWIT"}]
            reply = (
                "The machine comes to life with a dazzling display of colored lights and bizarre noises. "
                "After a few moments, the excitement abates."
            )
            if "COAL" in contents:
                object_locations.pop("COAL", None)
                object_locations.pop("GUNK", None)
                object_locations["DIAMO"] = "MACHINE"
                return (reply + " A huge diamond clunks into view.", flags, object_locations)
            if contents:
                for item_code in contents:
                    object_locations.pop(item_code, None)
                object_locations["GUNK"] = "MACHINE"
                return (reply + " What remains is an unimpressive piece of slag.", flags, object_locations)
            return (reply, flags, object_locations)

        return (f"You can't turn the {object_name(code_key)}.", flags, object_locations)

    def _light_action_response(self, session: dict[str, object], code: str, action: str) -> tuple[str, set[str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        inventory = set(self._session_inventory(session))
        counters = self._session_counters(session)

        fuel_code = self._balloon_fuel_code(session)
        fuel_target = ""
        if code_key == "RECEP":
            fuel_target = fuel_code
        elif fuel_code and code_key == fuel_code and str(object_locations.get(code_key) or "").strip().upper() == "RECEP":
            fuel_target = code_key
        if fuel_target:
            if action == "on":
                item = OBJECTS.get(fuel_target)
                if item is None or "BURNBIT" not in item.flags:
                    return (f"The {object_name(fuel_target)} won't burn usefully in the receptacle.", flags)
                if counters.get("balloon_burn_turns"):
                    return ("The receptacle is already occupied by a burning fire.", flags)
                if not (
                    "MATCH" in inventory
                    or self._object_is_lit(session, "TORCH")
                    or self._object_is_lit(session, "LAMP")
                    or self._object_is_lit(session, "CANDL")
                ):
                    return ("You need some kind of flame to light it.", flags)
                counters["balloon_burn_turns"] = self._balloon_fuel_duration(fuel_target)
                flags.add("balloon_inflated")
                return (
                    f"The {object_name(fuel_target)} burns inside the receptacle. The cloth bag inflates as it fills with hot air.",
                    flags,
                )
            if not counters.get("balloon_burn_turns"):
                return ("Nothing in the receptacle is burning.", flags)
            counters["balloon_burn_turns"] = 0
            flags.discard("balloon_inflated")
            return ("The fire in the receptacle dies, and the cloth bag starts to sag.", flags)

        if code_key == "LAMP":
            return self._lamp_response(session, action)

        if code_key == "TORCH":
            if not self._is_accessible(session, "TORCH"):
                return ("You have no torch handy.", flags)
            if action == "on":
                if "torch_burned_out" in flags:
                    return ("The torch has burned out completely.", flags)
                if "torch_unlit" not in flags:
                    return ("The torch is already burning.", flags)
                flags.discard("torch_unlit")
                return ("The torch flares back to life.", flags)
            if "torch_unlit" in flags or "torch_burned_out" in flags:
                return ("The torch is already out.", flags)
            flags.add("torch_unlit")
            return ("The torch gutters out.", flags)

        if code_key == "CANDL":
            if not self._is_accessible(session, "CANDL"):
                return ("You have no candles handy.", flags)
            if action == "on":
                if "candles_unlit" not in flags:
                    return ("The candles are already burning.", flags)
                if not (
                    self._object_is_lit(session, "TORCH")
                    or self._object_is_lit(session, "LAMP")
                    or "MATCH" in inventory
                ):
                    return ("You need some kind of flame to light the candles.", flags)
                flags.discard("candles_unlit")
                return ("The candles begin to burn again.", flags)
            if "candles_unlit" in flags:
                return ("The candles are already out.", flags)
            flags.add("candles_unlit")
            return ("The candles go out.", flags)

        return (f"You can't {'light' if action == 'on' else 'extinguish'} the {object_name(code_key)}.", flags)

    def _unlock_response(self, session: dict[str, object], code: str) -> tuple[str, set[str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        if code_key not in {"GRAT1", "GRAT2"}:
            return (f"You can't unlock the {object_name(code_key)}.", flags)
        if "KEYS" not in set(self._session_inventory(session)):
            return ("You need a key for that.", flags)
        if "grating_unlocked" in flags:
            return ("The grating is already unlocked.", flags)
        flags.add("grating_unlocked")
        return ("The grating unlocks with a satisfying click.", flags)

    def _wave_response(self, session: dict[str, object], code: str) -> tuple[str, set[str], dict[str, str], bool]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key != "STICK":
            return (f"Waving the {object_name(code_key)} accomplishes little.", flags, object_locations, False)
        if room_id in {"FALLS", "POG"}:
            if "rainbow_solid" not in flags:
                flags.add("rainbow_solid")
                return (
                    "Suddenly, the rainbow appears to become solid and, I venture, walkable.",
                    flags,
                    object_locations,
                    False,
                )
            flags.discard("rainbow_solid")
            return ("The rainbow seems to have become somewhat run-of-the-mill.", flags, object_locations, False)
        if room_id == "RAINB" and "rainbow_solid" in flags:
            flags.discard("rainbow_solid")
            return (
                "The structural integrity of the rainbow gives up and so do you. zork: session ended. Send 'zork' to start again.",
                flags,
                object_locations,
                True,
            )
        return ("Very good.", flags, object_locations, False)

    def _tie_or_untie_response(
        self,
        session: dict[str, object],
        code: str,
        anchor_code: str | None,
        action: str,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        anchor_key = str(anchor_code or "").strip().upper()
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key == "BROPE":
            tied_room = self._balloon_tied_room(session)
            expected_hook = BALLOON_HOOK_CODES.get(room_id, "")
            if action == "untie":
                if tied_room != room_id:
                    return ("The wire is not tied to anything.", inventory, flags, object_locations)
                flags.discard("balloon_tied_ledg2")
                flags.discard("balloon_tied_ledg4")
                return ("The wire falls off of the hook.", inventory, flags, object_locations)

            if room_id not in BALLOON_HOOK_CODES or object_locations.get("BALLO") != room_id:
                return ("There is nothing it can be tied to.", inventory, flags, object_locations)
            if anchor_key != expected_hook:
                return ("There is nothing it can be tied to.", inventory, flags, object_locations)
            if tied_room == room_id:
                return ("The balloon is fastened to the hook.", inventory, flags, object_locations)
            flags.discard("balloon_tied_ledg2")
            flags.discard("balloon_tied_ledg4")
            if room_id == "LEDG2":
                flags.add("balloon_tied_ledg2")
            if room_id == "LEDG4":
                flags.add("balloon_tied_ledg4")
            return ("The balloon is fastened to the hook.", inventory, flags, object_locations)

        if code_key != "ROPE":
            verb = "tie" if action == "tie" else "untie"
            return (f"You can't {verb} the {object_name(code_key)}.", inventory, flags, object_locations)

        if action == "untie":
            if room_id != "DOME" or "dome_rope_tied" not in flags:
                return ("It is not tied to anything.", inventory, flags, object_locations)
            flags.discard("dome_rope_tied")
            object_locations["ROPE"] = "DOME"
            return ("Although you tied it incorrectly, the rope becomes free.", inventory, flags, object_locations)

        if room_id != "DOME" or anchor_key != "RAILI":
            return ("There is nothing it can be tied to.", inventory, flags, object_locations)
        if "dome_rope_tied" in flags:
            return ("The rope is already attached.", inventory, flags, object_locations)
        inventory = [value for value in inventory if value != "ROPE"]
        object_locations["ROPE"] = "DOME"
        flags.add("dome_rope_tied")
        return (
            "The rope drops over the side and comes within ten feet of the floor below.",
            inventory,
            flags,
            object_locations,
        )

    def _magic_word_response(
        self,
        session: dict[str, object],
        word: str,
    ) -> tuple[str, str | None, set[str], dict[str, str], bool]:
        word_key = str(word or "").strip().lower()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if word_key == "well":
            if room_id in {"TWELL", "BWELL"}:
                other_room = "BWELL" if room_id == "TWELL" else "TWELL"
                bucket_room = str(object_locations.get("BUCKE") or "").strip().upper()
                if bucket_room == room_id and "aboard_bucket" in flags:
                    object_locations["BUCKE"] = other_room
                    if other_room == "BWELL":
                        return (
                            "The bucket creaks and descends into the darkness.",
                            other_room,
                            flags,
                            object_locations,
                            False,
                        )
                    return (
                        "The bucket rises slowly and comes to rest at the top of the well.",
                        other_room,
                        flags,
                        object_locations,
                        False,
                    )
                if bucket_room == room_id:
                    return ("The bucket is already here.", None, flags, object_locations, False)
                object_locations["BUCKE"] = room_id
                if room_id == "TWELL":
                    return (
                        "A wooden bucket rises out of the darkness and comes to rest beside the well.",
                        None,
                        flags,
                        object_locations,
                        False,
                    )
                return (
                    "A wooden bucket descends from above and comes to rest beside you.",
                    None,
                    flags,
                    object_locations,
                    False,
                )
            if room_id != "RIDDL":
                return ("Well what?", None, flags, object_locations, False)
            if "riddle_solved" in flags:
                return ("The stone door is already open.", None, flags, object_locations, False)
            flags.add("riddle_solved")
            return ("There is a clap of thunder and the east door opens.", None, flags, object_locations, False)
        if word_key == "sinbad":
            if room_id == "CYCLO" and "cyclops_gone" not in flags:
                flags.add("cyclops_gone")
                flags.add("magic_door_open")
                object_locations["CYCLO"] = "GONE"
                return (
                    "The cyclops, hearing the name of his deadly nemesis, flees by smashing down the north wall.",
                    None,
                    flags,
                    object_locations,
                    False,
                )
            return ("Wasn't he a sailor?", None, flags, object_locations, False)
        if word_key == "geronimo":
            if room_id == "BARRE":
                return (
                    "I didn't think you would REALLY try to go over the falls in a barrel. Some 450 feet below, you are met by unfriendly rocks and boulders. zork: session ended. Send 'zork' to start again.",
                    None,
                    flags,
                    object_locations,
                    True,
                )
            return ("Wasn't he an Apache?", None, flags, object_locations, False)
        return ("Nothing happens.", None, flags, object_locations, False)

    def _prayer_response(
        self,
        session: dict[str, object],
        now_unix: int,
    ) -> tuple[str, str | None, set[str], dict[str, str]]:
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if room_id == "TEMP2":
            return ("A feeling of holiness steals over you, and then you are elsewhere.", "FORE1", flags, object_locations)
        return ("If you pray enough, your prayers may be answered.", None, flags, object_locations)

    def _guardian_of_the_dungeon_death(self) -> str:
        return (
            "The voice of the guardian of the dungeon booms out from the darkness: "
            "'Your disrespect costs you your life!' and places your head on a pole. "
            "zork: session ended. Send 'zork' to start again."
        )

    def _begone_chomper_death(self) -> str:
        return (
            "There is a clap of thunder, and a voice echoes through the cavern: 'Begone, chomper!' "
            "Apparently, the voice thinks you are an evil spirit, and dismisses you from the realm of the living. "
            "zork: session ended. Send 'zork' to start again."
        )

    def _exorcise_response(self, session: dict[str, object]) -> tuple[str, set[str], dict[str, str], bool]:
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = set(self._session_inventory(session))
        visible = set(self._visible_top_level_objects(session, room_id))
        if room_id != "LLD1":
            return ("That would be overdramatic here.", flags, object_locations, False)
        if "GHOST" not in visible:
            return (self._begone_chomper_death(), flags, object_locations, True)
        required = {"BELL", "BOOK", "CANDL"}
        if not required.issubset(inventory) or not self._object_is_lit(session, "CANDL"):
            return ("You are not equipped for an exorcism.", flags, object_locations, False)
        flags.add("lld_open")
        object_locations["GHOST"] = "GONE"
        return (
            "There is a clap of thunder, and a voice echoes through the cavern: 'Begone, fiends!' The spirits, sensing the presence of a greater power, flee through the walls.",
            flags,
            object_locations,
            False,
        )

    def _gnome_exchange_response(
        self,
        session: dict[str, object],
        offered_code: str,
        *,
        action: str,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        code_key = str(offered_code or "").strip().upper()
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key not in inventory:
            return (f"You aren't carrying the {object_name(code_key)}.", inventory, flags, object_locations)
        if room_id not in GNOME_LEDGE_ROOMS or str(object_locations.get("GNOME") or "").strip().upper() != room_id:
            return ("The volcano gnome is not here.", inventory, flags, object_locations)

        counters = self._session_counters(session)
        inventory = [value for value in inventory if value != code_key]
        object_locations[code_key] = "GONE"
        if self._is_treasure(code_key):
            flags.add("gnome_door_open")
            object_locations["GNOME"] = "GONE"
            counters["gnome_nervous_turns"] = 0
            counters["gnome_depart_turns"] = 0
            return (
                f"'Thank you very much for the {object_name(code_key)}. Follow me,' says the gnome. A small door appears on the west side of the ledge, opening onto a narrow chimney sloping downward.",
                inventory,
                flags,
                object_locations,
            )
        return (
            f"'That wasn't quite what I had in mind,' says the gnome, crunching the {object_name(code_key)} in his rock-hard hands.",
            inventory,
            flags,
            object_locations,
        )

    def _give_response(
        self,
        session: dict[str, object],
        code: str,
        target_code: str,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        target_key = str(target_code or "").strip().upper()
        if target_key == "GNOME":
            return self._gnome_exchange_response(session, code, action="give")
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        return (f"The {object_name(target_key)} doesn't seem interested.", inventory, flags, object_locations)

    def _put_or_insert_response(
        self,
        session: dict[str, object],
        code: str,
        container_code: str,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        container_key = str(container_code or "").strip().upper()
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key not in inventory:
            return (f"You aren't carrying the {object_name(code_key)}.", inventory, flags, object_locations)
        if not self._target_may_be_addressed(session, container_key, "put"):
            return (f"You don't see any {object_name(container_key)} here.", inventory, flags, object_locations)
        if code_key == container_key:
            return ("That would be a neat topological trick, but no.", inventory, flags, object_locations)

        if container_key == "RECEP":
            if room_id not in BALLOON_GROUND_ROOMS | BALLOON_AIR_ROOMS:
                return ("The receptacle is not here.", inventory, flags, object_locations)
            if object_locations.get("BALLO") != room_id:
                return ("The balloon is not here.", inventory, flags, object_locations)
            if self._balloon_fuel_code(session):
                return ("The receptacle is already occupied.", inventory, flags, object_locations)
            item = OBJECTS.get(code_key)
            if item is None or "BURNBIT" not in item.flags:
                return ("That wouldn't make useful balloon fuel.", inventory, flags, object_locations)
            inventory = [value for value in inventory if value != code_key]
            object_locations[code_key] = "RECEP"
            return (f"The {object_name(code_key)} is now in the receptacle.", inventory, flags, object_locations)

        if container_key == "MACHI":
            if room_id != "MACHI":
                return ("The machine is not here.", inventory, flags, object_locations)
            if "machine_open" not in flags:
                return ("The lid is closed.", inventory, flags, object_locations)
            inventory = [value for value in inventory if value != code_key]
            object_locations[code_key] = "MACHINE"
            return (f"The {object_name(code_key)} is now in the machine.", inventory, flags, object_locations)

        if container_key in {"BRICK"}:
            if code_key != "FUSE":
                return (f"You can't put the {object_name(code_key)} into the {object_name(container_key)}.", inventory, flags, object_locations)
            inventory = [value for value in inventory if value != code_key]
            object_locations["FUSE"] = "BRICK"
            return ("The wire is now threaded through the brick.", inventory, flags, object_locations)

        if container_key in {"SSLOT", "SAFE"}:
            if code_key != "BRICK":
                return ("Only the brick seems likely to fit there usefully.", inventory, flags, object_locations)
            if room_id != "SAFE":
                return ("That slot is not here.", inventory, flags, object_locations)
            inventory = [value for value in inventory if value != code_key]
            object_locations["BRICK"] = "SSLOT"
            if object_locations.get("FUSE") == "BRICK":
                object_locations["FUSE"] = "SSLOT"
            return ("The brick slides neatly into the slot.", inventory, flags, object_locations)

        if container_key == "LEAK":
            if code_key != "PUTTY":
                return ("Only putty seems likely to stop that leak.", inventory, flags, object_locations)
            if room_id != "MAINT":
                return ("There is no leak here.", inventory, flags, object_locations)
            if "maintenance_leak_active" not in flags:
                return ("There is no active leak to plug.", inventory, flags, object_locations)
            flags.discard("maintenance_leak_active")
            return (
                "By some miracle of elven technology, you have managed to stop the leak in the dam.",
                inventory,
                flags,
                object_locations,
            )

        container_item = OBJECTS.get(container_key)
        if container_item is None or "CONTBIT" not in container_item.flags:
            return (f"You can't put the {object_name(code_key)} into the {object_name(container_key)}.", inventory, flags, object_locations)
        if not self._container_open(container_key, flags):
            return (f"The {object_name(container_key)} is closed.", inventory, flags, object_locations)

        inventory = [value for value in inventory if value != code_key]
        object_locations[code_key] = self._container_location_code(container_key)
        if container_key == "TCASE":
            return (f"The {object_name(code_key)} is now in the trophy case.", inventory, flags, object_locations)
        return (f"The {object_name(code_key)} is now in the {object_name(container_key)}.", inventory, flags, object_locations)

        return (f"You can't put the {object_name(code_key)} into the {object_name(container_key)}.", inventory, flags, object_locations)

    def _rub_response(
        self,
        session: dict[str, object],
        code: str,
    ) -> tuple[str, str | None, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if code_key not in {"REFL1", "REFL2"}:
            return (f"Rubbing the {object_name(code_key)} accomplishes little.", None, flags, object_locations)
        if "mirror_broken" in flags:
            return ("The mirror is broken into many pieces.", None, flags, object_locations)
        if room_id not in {"MIRR1", "MIRR2"}:
            return ("There is no mirror here worth rubbing.", None, flags, object_locations)
        other_room = "MIRR2" if room_id == "MIRR1" else "MIRR1"
        for item_code, location in list(object_locations.items()):
            if location == room_id and item_code not in {"REFL1", "REFL2"}:
                object_locations[item_code] = other_room
            elif location == other_room and item_code not in {"REFL1", "REFL2"}:
                object_locations[item_code] = room_id
        return ("There is a rumble from deep within the earth and the room shakes.", other_room, flags, object_locations)

    def _throw_response(
        self,
        session: dict[str, object],
        code: str,
        target_code: str | None,
    ) -> tuple[str, str | None, list[str], set[str], dict[str, str], bool]:
        code_key = str(code or "").strip().upper()
        target_key = str(target_code or "").strip().upper()
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key not in inventory:
            return (f"You aren't carrying the {object_name(code_key)}.", None, inventory, flags, object_locations, False)

        if target_key == "GNOME":
            reply, inventory, flags, object_locations = self._gnome_exchange_response(session, code_key, action="throw")
            return (reply, None, inventory, flags, object_locations, False)

        if target_key == "GHOST":
            visible = set(self._visible_top_level_objects(session, room_id))
            if "GHOST" in visible:
                return (
                    "How can you attack a spirit with material objects?",
                    None,
                    inventory,
                    flags,
                    object_locations,
                    False,
                )

        if code_key == "FLASK":
            inventory = [value for value in inventory if value != "FLASK"]
            object_locations["FLASK"] = "GONE"
            return (
                "The flask breaks into pieces. Just before you pass out, you notice that the vapors from the flask's contents are fatal. zork: session ended. Send 'zork' to start again.",
                None,
                inventory,
                flags,
                object_locations,
                True,
            )

        if room_id.startswith("ALI") and code_key == "ORICE":
            inventory = [value for value in inventory if value != "ORICE"]
            object_locations["ORICE"] = "GONE"
            return (
                "The orange cake explodes into sticky rubble and you are blasted to smithereens. zork: session ended. Send 'zork' to start again.",
                None,
                inventory,
                flags,
                object_locations,
                True,
            )

        if room_id == "ALITR" and code_key == "RDICE" and target_key == "POOL":
            inventory = [value for value in inventory if value != "RDICE"]
            object_locations["RDICE"] = "GONE"
            flags.add("pool_evaporated")
            object_locations["POOL"] = "GONE"
            object_locations["SAFFR"] = "ALITR"
            return (
                "The pool of water evaporates, revealing a tin of rare spices.",
                None,
                inventory,
                flags,
                object_locations,
                False,
            )

        if room_id == "ICY" and code_key == "TORCH" and target_key == "ICE":
            inventory = [value for value in inventory if value != "TORCH"]
            flags.add("glacier_melted")
            flags.add("torch_unlit")
            flags.add("torch_burned_out")
            object_locations["TORCH"] = "STREA"
            object_locations["ICE"] = "GONE"
            reply = (
                "The torch hits the glacier and explodes into a great ball of flame, devouring the glacier. "
                "The water from the melting glacier rushes downstream, carrying the torch with it. "
                "In the place of the glacier there is now a passageway leading west."
            )
            return (reply, None, inventory, flags, object_locations, False)

        if target_key in {"REFL1", "REFL2"}:
            flags.add("mirror_broken")
            inventory = [value for value in inventory if value != code_key]
            object_locations[code_key] = room_id
            return (
                "You have broken the mirror. I hope you have a seven years supply of good luck handy.",
                None,
                inventory,
                flags,
                object_locations,
                False,
            )

        inventory = [value for value in inventory if value != code_key]
        object_locations[code_key] = room_id
        return (f"Thrown. The {object_name(code_key)} clatters to the floor.", None, inventory, flags, object_locations, False)

    def _light_fuse_response(self, session: dict[str, object]) -> tuple[str, set[str], dict[str, str]]:
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        inventory = set(self._session_inventory(session))
        counters = self._session_counters(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        if room_id != "SAFE":
            return ("Lighting a loose fuse seems unwise.", flags, object_locations)
        if object_locations.get("BRICK") != "SSLOT" or object_locations.get("FUSE") != "SSLOT":
            return ("The fuse isn't set up for anything useful yet.", flags, object_locations)
        if int(counters.get("fuse_turns") or 0) > 0 or "fuse_lit" in flags:
            return ("The wire is already burning merrily away.", flags, object_locations)
        if not (
            "MATCH" in inventory
            or self._object_is_lit(session, "TORCH")
            or self._object_is_lit(session, "LAMP")
            or self._object_is_lit(session, "CANDL")
        ):
            return ("You need a flame to light the fuse.", flags, object_locations)
        flags.add("fuse_lit")
        counters["fuse_turns"] = 2
        return (
            "The wire starts to burn.",
            flags,
            object_locations,
        )

    def _repair_or_plug_response(
        self,
        session: dict[str, object],
        code: str,
        tool_code: str | None,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        tool_key = str(tool_code or "").strip().upper()
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM

        if code_key == "RBOAT":
            return ("The boat is already inflated and in one piece.", inventory, flags, object_locations)
        if code_key == "IBOAT":
            return ("The boat isn't damaged.", inventory, flags, object_locations)
        if code_key == "LEAK":
            if room_id != "MAINT":
                return ("There is no leak here.", inventory, flags, object_locations)
            if "maintenance_leak_active" not in flags:
                return ("There is no leak to plug.", inventory, flags, object_locations)
            if tool_key and tool_key != "PUTTY":
                return (f"With a {object_name(tool_key)}?", inventory, flags, object_locations)
            if tool_key != "PUTTY":
                return ("You'll need something like putty to plug the leak.", inventory, flags, object_locations)
            if "PUTTY" not in set(inventory):
                return ("You need some putty for that.", inventory, flags, object_locations)
            flags.discard("maintenance_leak_active")
            return (
                "By some miracle of elven technology, you have managed to stop the leak in the dam.",
                inventory,
                flags,
                object_locations,
            )
        if code_key != "DBOAT":
            return (f"You can't repair the {object_name(code_key)} that way.", inventory, flags, object_locations)
        if "DBOAT" not in inventory and object_locations.get("DBOAT") != room_id:
            return ("The damaged boat is not here.", inventory, flags, object_locations)
        if tool_key and tool_key != "PUTTY":
            return (f"The {object_name(tool_key)} will not make the boat airtight.", inventory, flags, object_locations)
        if tool_key != "PUTTY":
            return ("You'll need something like putty to repair the hole.", inventory, flags, object_locations)
        if "PUTTY" not in set(inventory):
            return ("You need some putty for that.", inventory, flags, object_locations)
        if "DBOAT" in inventory:
            inventory = [value for value in inventory if value != "DBOAT"]
            inventory.append("IBOAT")
            object_locations["DBOAT"] = "GONE"
            object_locations["IBOAT"] = "INVENTORY"
            return ("Well done. The boat is repaired.", inventory, flags, object_locations)
        object_locations["DBOAT"] = "GONE"
        object_locations["IBOAT"] = room_id
        return ("Well done. The boat is repaired.", inventory, flags, object_locations)

    def _board_or_disembark_response(
        self,
        session: dict[str, object],
        action: str,
        target_code: str | None = None,
    ) -> tuple[str, list[str], set[str], dict[str, str]]:
        inventory = self._session_inventory(session)
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        target_key = str(target_code or "RBOAT").strip().upper() or "RBOAT"

        if action == "board":
            if target_key == "IBOAT":
                return ("It would be more useful if it were inflated.", inventory, flags, object_locations)
            if target_key == "DBALL":
                return ("It would be more useful if it were not shattered.", inventory, flags, object_locations)
            if target_key == "BUCKE":
                if "aboard_bucket" in flags:
                    return ("You are already in the bucket.", inventory, flags, object_locations)
                if object_locations.get("BUCKE") != room_id:
                    return ("You don't see any bucket here.", inventory, flags, object_locations)
                flags.discard("aboard_boat")
                flags.discard("aboard_balloon")
                flags.add("aboard_bucket")
                return ("You are now in the bucket.", inventory, flags, object_locations)
            if target_key == "BALLO":
                if "aboard_balloon" in flags:
                    return ("You are already in the balloon.", inventory, flags, object_locations)
                if object_locations.get("BALLO") != room_id:
                    return ("You don't see any balloon here.", inventory, flags, object_locations)
                flags.discard("aboard_boat")
                flags.discard("aboard_bucket")
                flags.add("aboard_balloon")
                return ("You are now in the balloon basket.", inventory, flags, object_locations)
            if target_key != "RBOAT":
                return (f"You can't board the {object_name(target_key)}.", inventory, flags, object_locations)
            if "aboard_boat" in flags:
                return ("You are already in the boat.", inventory, flags, object_locations)
            if "RBOAT" in inventory:
                inventory = [value for value in inventory if value != "RBOAT"]
                object_locations["RBOAT"] = room_id
            if object_locations.get("RBOAT") != room_id:
                return ("You don't see any inflated boat here.", inventory, flags, object_locations)
            if "STICK" in inventory:
                object_locations["RBOAT"] = "GONE"
                object_locations["DBOAT"] = room_id
                flags.discard("aboard_boat")
                return ("There is a hissing sound and the boat deflates.", inventory, flags, object_locations)
            flags.discard("aboard_balloon")
            flags.discard("aboard_bucket")
            flags.add("aboard_boat")
            return ("You are now in the magic boat.", inventory, flags, object_locations)

        if "aboard_balloon" in flags:
            if room_id in BALLOON_AIR_ROOMS:
                return ("This is no place to be getting out of the balloon.", inventory, flags, object_locations)
            flags.discard("aboard_balloon")
            return ("You climb out of the balloon basket.", inventory, flags, object_locations)

        if "aboard_bucket" in flags:
            flags.discard("aboard_bucket")
            return ("You climb out of the bucket.", inventory, flags, object_locations)

        if "aboard_boat" not in flags:
            return ("You are not in any vehicle.", inventory, flags, object_locations)
        if self._is_river_room(room_id):
            return ("The river is no place to be getting out of the boat.", inventory, flags, object_locations)
        flags.discard("aboard_boat")
        return ("You are on your own feet again.", inventory, flags, object_locations)

    def _inflate_deflate_response(self, session: dict[str, object], code: str, action: str) -> tuple[str, set[str], dict[str, str]]:
        code_key = str(code or "").strip().upper()
        flags = self._session_flags(session)
        object_locations = self._object_locations(session)
        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        inventory = set(self._session_inventory(session))

        if action == "inflate":
            if code_key == "DBOAT":
                return ("This boat will not inflate since some moron put a hole in it.", flags, object_locations)
            if code_key != "IBOAT":
                return (f"You can't inflate the {object_name(code_key)}.", flags, object_locations)
            if object_locations.get("IBOAT") != room_id:
                return ("The boat must be on the ground to be inflated.", flags, object_locations)
            if "PUMP" not in inventory:
                return ("I don't think you have enough lung-power to inflate this boat.", flags, object_locations)
            object_locations["IBOAT"] = "GONE"
            object_locations["RBOAT"] = room_id
            return ("The boat inflates and appears seaworthy.", flags, object_locations)

        if code_key != "RBOAT":
            return (f"You can't deflate the {object_name(code_key)}.", flags, object_locations)
        if "aboard_boat" in flags:
            return ("You'll have to get out of the boat first.", flags, object_locations)
        if object_locations.get("RBOAT") != room_id:
            return ("The boat must be on the ground to be deflated.", flags, object_locations)
        object_locations["RBOAT"] = "GONE"
        object_locations["IBOAT"] = room_id
        return ("The boat deflates.", flags, object_locations)

    def try_handle_message(
        self,
        *,
        text: str,
        from_id: str,
        to_id: str,
        local_node_id: str,
        now_unix: int,
        enabled: bool,
    ) -> BotAppResult:
        raw = str(text or "").strip()
        if not raw:
            return BotAppResult(handled=False)
        robot_command = self._extract_robot_command(raw)
        if robot_command is not None:
            parts = ["robot", *[part for part in robot_command.split() if part]]
            head_raw = "robot"
        else:
            parts = [part for part in raw.split() if part]
            if not parts:
                return BotAppResult(handled=False)
            head_raw = str(parts[0]).strip().lower()
        if head_raw not in GAME_VERB_HEADS:
            return BotAppResult(handled=False)
        if not self._is_direct_to_local(to_id, local_node_id):
            return BotAppResult(handled=False)

        peer_id = str(from_id or "").strip().lower()
        if not peer_id.startswith("!"):
            return BotAppResult(handled=False)

        self._prune_sessions(now_unix)
        session = self._sessions.get(peer_id)
        if head_raw in ("zork", "!zork", "#zork", "restart"):
            if not enabled:
                return BotAppResult(handled=True, command_name=self.SPEC.name)
            session = self._start_session(from_id, now_unix)
            self._mark_room_seen(session, START_ROOM)
            summary = self._room_summary(session, START_ROOM, explicit_look=True)
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"zork: session started. {summary} {START_HELP_HINT}"),
                command_name=self.SPEC.name,
            )

        if session is None:
            return BotAppResult(handled=False)
        if not enabled:
            return BotAppResult(handled=True, command_name=self.SPEC.name)

        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        inventory = self._session_inventory(session)
        object_locations = self._object_locations(session)
        args = [str(value).strip().lower() for value in parts[1:] if str(value).strip()]
        raw_target = " ".join(args)

        pending_event = self._handle_pending_turn_events(session, now_unix=now_unix)
        if pending_event is not None:
            return pending_event

        room_id = str(session.get("room") or START_ROOM).strip().upper() or START_ROOM
        flags = self._session_flags(session)
        inventory = self._session_inventory(session)
        object_locations = self._object_locations(session)

        if room_id == "CAGED" and "cage_solved" not in flags:
            robot_raising = False
            if robot_command:
                robot_words = self._clean_words(robot_command)
                robot_raising = bool(robot_words and robot_words[0] == "raise")
            if not robot_raising:
                counters = self._session_counters(session)
                remaining = int(counters.get("cage_gas_turns") or 10) - 1
                counters["cage_gas_turns"] = remaining
                if remaining <= 0:
                    self._sessions.pop(peer_id, None)
                    return BotAppResult(
                        handled=True,
                        reply_text="Time passes...and you die from some obscure poisoning. zork: session ended. Send 'zork' to start again.",
                        command_name=self.SPEC.name,
                    )

        if self._room_is_dark(session, room_id) and head_raw not in {
            "north",
            "n",
            "south",
            "s",
            "east",
            "e",
            "west",
            "w",
            "up",
            "u",
            "down",
            "d",
            "ne",
            "nw",
            "se",
            "sw",
            "enter",
            "in",
            "exit",
            "out",
            "go",
            "walk",
            "inventory",
            "inv",
            "i",
            "light",
            "burn",
            "turn",
            "on",
            "off",
            "extinguish",
            "wave",
            "tie",
            "untie",
            "inflate",
            "deflate",
            "push",
            "press",
            "board",
            "disembark",
            "put",
            "insert",
            "plug",
            "repair",
            "patch",
            "raise",
            "lower",
            "throw",
            "rub",
            "melt",
            "well",
            "sinbad",
            "help",
            "score",
            "quit",
            "exitgame",
            "restart",
            "zork",
            "!zork",
            "#zork",
            "look",
            "l",
        }:
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text="It is pitch black. You are likely to be eaten by a grue.", command_name=self.SPEC.name)

        if head_raw == "robot":
            reply, room_after, inventory, flags, object_locations, ended = self._robot_command_response(session, robot_command or "")
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)

        if head_raw in {"help"}:
            return BotAppResult(
                handled=True,
                reply_text=(
                    "zork: look, x/read, read <cake> through flask, eat, n/s/e/w/u/d, take/drop/give, put/insert, throw/rub, open/close, move, push/press, turn, "
                    "light/burn/extinguish, dig, wave stick, tie/untie rope or balloon wire, raise/lower basket, plug/repair broken boat or leak, inflate/deflate boat, board/disembark, launch/land, pray/exorcise, "
                    "robot, press <button>; robot, north/east/etc.; robot, take sphere; robot, raise cage; magic words, score, attack, quit."
                ),
                command_name=self.SPEC.name,
            )

        if head_raw == "score":
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._score_text(session), command_name=self.SPEC.name)

        if head_raw in {"quit", "exitgame"}:
            score_text = self._score_text(session)
            self._sessions.pop(peer_id, None)
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"{score_text} zork: session ended. Send 'zork' to start again."),
                command_name=self.SPEC.name,
            )

        if head_raw in {"board", "disembark"}:
            target_text = raw_target or (self._default_board_target(session) if head_raw == "board" else "")
            target = self._resolve_object(session, target_text, head_raw) if target_text else None
            reply, inventory, flags, object_locations = self._board_or_disembark_response(session, head_raw, target)
            self._write_session_state(
                session,
                room_id=room_id,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
                now_unix=now_unix,
            )
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"),
                command_name=self.SPEC.name,
            )

        direction = self._movement_direction(head_raw, args)
        if direction is not None:
            return self._move(session, direction, now_unix)

        if head_raw in {"look", "l"}:
            if args[:1] == ["under"] and len(args) > 1:
                target = self._resolve_object(session, " ".join(args[1:]), "look")
                if target == "RUG" and room_id == "LROOM":
                    if "rug_moved" in flags or "trap_door_open" in flags:
                        reply = "The trap door is already exposed."
                    else:
                        reply = "Under the rug is a closed trap door."
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
                if target == "LEAVE" and room_id == "CLEAR":
                    reply = "Under the leaves is a grating." if "leaves_moved" not in flags else "The grating is already exposed."
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text="You find nothing of interest.", command_name=self.SPEC.name)
            if args and args[0] == "at":
                raw_target = " ".join(args[1:])
            if raw_target:
                target = self._resolve_object(session, raw_target, "look")
                reply = self._describe_object(session, target) if target else f"You don't see any {raw_target} here."
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._room_summary(session, room_id, explicit_look=True), command_name=self.SPEC.name)

        if head_raw in {"examine", "x"}:
            target = self._resolve_object(session, raw_target, "examine")
            reply = self._describe_object(session, target) if target else (f"You don't see any {raw_target} here." if raw_target else "Examine what?")
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)

        if head_raw in {"inventory", "inv", "i"}:
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._inventory_text(session), command_name=self.SPEC.name)

        if head_raw == "read":
            target_text = raw_target
            viewer_text = ""
            for separator in (" through ", " with ", " using "):
                if separator in f" {raw_target} ":
                    before, after = raw_target.split(separator, 1)
                    target_text = before.strip()
                    viewer_text = after.strip()
                    break
            target = self._resolve_object(session, target_text, "read")
            viewer = self._resolve_object(session, viewer_text, "read") if viewer_text else None
            reply = self._read_object(session, target, viewer) if target else (f"You don't see any {target_text or raw_target} here." if raw_target else "Read what?")
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)

        if head_raw == "eat":
            target = self._resolve_object(session, raw_target, "eat")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Eat what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, room_after, inventory, flags, object_locations, ended = self._eat_response(session, target)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            room_after = room_after or room_id
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)

        if head_raw in {"plug", "repair", "patch"}:
            direct_text = raw_target
            tool_text = ""
            if " with " in f" {raw_target} ":
                before, after = raw_target.split(" with ", 1)
                direct_text = before.strip()
                tool_text = after.strip()
            target_text = direct_text or "boat"
            target = self._resolve_object(session, target_text, head_raw)
            tool = self._resolve_object(session, tool_text, head_raw) if tool_text else ("PUTTY" if "PUTTY" in inventory else None)
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {target_text} here." if raw_target else ("Repair what?" if head_raw == "repair" else "Plug what?")
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, inventory, flags, object_locations = self._repair_or_plug_response(session, target, tool)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "give":
            direct_text = raw_target
            target_text = ""
            if " to " in f" {raw_target} ":
                before, after = raw_target.split(" to ", 1)
                direct_text = before.strip()
                target_text = after.strip()
            direct = self._resolve_object(session, direct_text, "give") if direct_text else None
            target = self._resolve_object(session, target_text, "give") if target_text else ("GNOME" if self._is_accessible(session, "GNOME") else None)
            if not direct:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You aren't carrying {direct_text}." if direct_text else "Give what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = "Give it to whom?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, inventory, flags, object_locations = self._give_response(session, direct, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"put", "insert"}:
            direct_text = raw_target
            container_text = ""
            for separator in (" into ", " in ", " inside ", " on "):
                if separator in f" {raw_target} ":
                    before, after = raw_target.split(separator, 1)
                    direct_text = before.strip()
                    container_text = after.strip()
                    break
            container = self._resolve_object(session, container_text, "put") if container_text else None
            if not container:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = "Put it where?" if not direct_text else f"Where do you want to put {direct_text}?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)

            direct_scope = self._bulk_scope(direct_text)
            if direct_scope:
                candidates = self._bulk_inventory_candidates(session, treasure_only=direct_scope == "treasures")
                if not candidates:
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    reply = "You aren't carrying any valuables." if direct_scope == "treasures" else "You aren't carrying anything worth putting."
                    return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
                moved: list[str] = []
                blocked_reply = ""
                for code in candidates:
                    working = self._ephemeral_session(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                    )
                    old_inventory = set(inventory)
                    item_reply, inventory, flags, object_locations = self._put_or_insert_response(working, code, container)
                    if code in old_inventory and code not in set(inventory):
                        moved.append(code)
                    elif not blocked_reply:
                        blocked_reply = item_reply
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                if moved:
                    reply = f"Stored: {', '.join(object_name(code) for code in moved)}."
                    if blocked_reply:
                        reply = f"{reply} {blocked_reply}"
                    return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)
                return BotAppResult(handled=True, reply_text=self._compact(blocked_reply or "Nothing fit."), command_name=self.SPEC.name)

            direct = self._resolve_object(session, direct_text, "put") if direct_text else None
            if not direct:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You aren't carrying {direct_text}." if direct_text else "Put what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, inventory, flags, object_locations = self._put_or_insert_response(session, direct, container)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "rub":
            target = self._resolve_object(session, raw_target, "rub")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Rub what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, new_room, flags, object_locations = self._rub_response(session, target)
            room_after = new_room or room_id
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)

        if head_raw == "melt":
            target = self._resolve_object(session, raw_target, "melt")
            if target == "ICE":
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text="How exactly are you going to melt this glacier?", command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text="That doesn't look especially meltable.", command_name=self.SPEC.name)

        if head_raw == "throw":
            direct_text = raw_target
            target_text = ""
            for separator in (" at ", " to ", " into ", " in ", " onto ", " on "):
                if separator in f" {raw_target} ":
                    before, after = raw_target.split(separator, 1)
                    direct_text = before.strip()
                    target_text = after.strip()
                    break
            direct = self._resolve_object(session, direct_text, "throw") if direct_text else None
            target = self._resolve_object(session, target_text, "throw") if target_text else None
            if not direct:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You aren't carrying {direct_text}." if direct_text else "Throw what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, new_room, inventory, flags, object_locations, ended = self._throw_response(session, direct, target)
            room_after = new_room or room_id
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)

        if head_raw in {"open", "close"}:
            target = self._resolve_object(session, raw_target, head_raw)
            if not target:
                reply = (f"You don't see any {raw_target} here." if raw_target else ("Open what?" if head_raw == "open" else "Close what?"))
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            if head_raw == "open" and target == "FLASK":
                self._sessions.pop(peer_id, None)
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(
                        "Noxious vapors prevent your entry. Just before you pass out, you notice that the vapors from the flask's contents are fatal. zork: session ended. Send 'zork' to start again."
                    ),
                    command_name=self.SPEC.name,
                )
            reply, flags, object_locations = self._open_close_response(session, target, head_raw)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "unlock":
            target = self._resolve_object(session, raw_target, "unlock")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Unlock what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags = self._unlock_response(session, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"move", "lift"}:
            target = self._resolve_object(session, raw_target, "move")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Move what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags, object_locations = self._move_or_lift_response(session, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"raise", "lower"}:
            target_text = raw_target.strip()
            if not target_text and room_id in {"TSHAF", "BSHAF"} and self._shaft_basket_here(session, room_id):
                target_text = "basket"
            target = self._resolve_object(session, target_text, head_raw) if target_text else None
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {target_text} here." if target_text else ("Raise what?" if head_raw == "raise" else "Lower what?")
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags, object_locations = self._raise_lower_response(session, head_raw, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "dig":
            tool_text = raw_target
            if " with " in f" {raw_target} ":
                _, after = raw_target.split(" with ", 1)
                tool_text = after.strip()
            tool = self._resolve_object(session, tool_text, "dig") if tool_text else None
            if tool != "SHOVE" and "SHOVE" in set(inventory):
                tool = "SHOVE"
            reply, flags, object_locations, ended = self._dig_response(session, tool)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "wave":
            target = self._resolve_object(session, raw_target, "wave")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Wave what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags, object_locations, ended = self._wave_response(session, target)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"tie", "untie"}:
            direct_text = raw_target
            anchor_text = ""
            if head_raw == "tie":
                if " to " in f" {raw_target} ":
                    before, after = raw_target.split(" to ", 1)
                    direct_text = before.strip()
                    anchor_text = after.strip()
                elif len(args) >= 2:
                    direct_text = " ".join(args[:-1])
                    anchor_text = args[-1]
            target = self._resolve_object(session, direct_text, head_raw)
            anchor = self._resolve_object(session, anchor_text, head_raw) if anchor_text else None
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {direct_text} here." if direct_text else ("Tie what?" if head_raw == "tie" else "Untie what?")
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, inventory, flags, object_locations = self._tie_or_untie_response(session, target, anchor, head_raw)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"take", "get"}:
            bulk_scope = self._bulk_scope(raw_target)
            if bulk_scope:
                candidates = self._bulk_take_candidates(session, treasure_only=bulk_scope == "treasures")
                if not candidates:
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    reply = "You see no valuables here." if bulk_scope == "treasures" else "There is nothing here worth taking."
                    return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
                moved: list[str] = []
                for code in candidates:
                    working = self._ephemeral_session(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                    )
                    reply, inventory, object_locations, flags = self._take_response(working, code)
                    if code in set(inventory):
                        moved.append(code)
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"Taken: {', '.join(object_name(code) for code in moved)}."
                return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)
            target = self._resolve_object(session, raw_target, "take")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else "Take what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            if target == "SPHER":
                reply, room_after, inventory, flags, object_locations, ended = self._sphere_take_response(session)
                if ended:
                    self._sessions.pop(peer_id, None)
                    return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
                suffix = self._room_summary_for_state(
                    session,
                    room_id=room_after,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)
            reply, inventory, object_locations, flags = self._take_response(session, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "drop":
            bulk_scope = self._bulk_scope(raw_target)
            if bulk_scope:
                candidates = self._bulk_inventory_candidates(session, treasure_only=bulk_scope == "treasures")
                if not candidates:
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    reply = "You aren't carrying any valuables." if bulk_scope == "treasures" else "You aren't carrying anything."
                    return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
                moved: list[str] = []
                blocked_reply = ""
                for code in candidates:
                    working = self._ephemeral_session(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                    )
                    old_inventory = set(inventory)
                    item_reply, inventory, object_locations, flags = self._drop_response(working, code)
                    if code in old_inventory and code not in set(inventory):
                        moved.append(code)
                    elif not blocked_reply:
                        blocked_reply = item_reply
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                if moved:
                    reply = f"Dropped: {', '.join(object_name(code) for code in moved)}."
                    if blocked_reply:
                        reply = f"{reply} {blocked_reply}"
                    return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)
                return BotAppResult(handled=True, reply_text=self._compact(blocked_reply or "Nothing was dropped."), command_name=self.SPEC.name)
            target = self._resolve_object(session, raw_target, "drop")
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You aren't carrying {raw_target}." if raw_target else "Drop what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, inventory, object_locations, flags = self._drop_response(session, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"inflate", "deflate"}:
            target_text = raw_target or "boat"
            target = self._resolve_object(session, target_text, head_raw)
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {target_text} here." if raw_target else ("Inflate what?" if head_raw == "inflate" else "Deflate what?")
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags, object_locations = self._inflate_deflate_response(session, target, head_raw)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"push", "press"}:
            target = self._resolve_object(session, raw_target, head_raw)
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {raw_target} here." if raw_target else f"{head_raw.title()} what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            if room_id == "CMACH" and target in {"SQBUT", "RNBUT", "TRBUT"}:
                self._sessions.pop(peer_id, None)
                return BotAppResult(
                    handled=True,
                    reply_text="There is a giant spark and you are fried to a crisp. zork: session ended. Send 'zork' to start again.",
                    command_name=self.SPEC.name,
                )
            reply, flags, object_locations = self._push_or_press_response(session, target)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "turn":
            if args[:1] in [["on"], ["off"]]:
                action = "on" if args[0] == "on" else "off"
                target_text = " ".join(args[1:]).strip() or "lamp"
                target = self._resolve_object(session, target_text, head_raw)
                if not target:
                    self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                    return BotAppResult(handled=True, reply_text=f"You don't see any {target_text} here.", command_name=self.SPEC.name)
                reply, flags = self._light_action_response(session, target, action)
                if room_id == "BOOM":
                    boom_ghost = self._ephemeral_session(
                        session,
                        room_id=room_id,
                        inventory=inventory,
                        flags=flags,
                        object_locations=object_locations,
                    )
                    if self._open_flame_present(boom_ghost):
                        self._sessions.pop(peer_id, None)
                        return BotAppResult(
                            handled=True,
                            reply_text=self._compact(
                                "Oh dear. It appears that the smell coming from this room was coal gas. "
                                "Carrying an open flame in here was a catastrophically bad plan. "
                                "BOOOOOOOOOOOM. zork: session ended. Send 'zork' to start again."
                            ),
                            command_name=self.SPEC.name,
                        )
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

            direct_text = raw_target
            tool_text = ""
            if " with " in f" {raw_target} ":
                before, after = raw_target.split(" with ", 1)
                direct_text = before.strip()
                tool_text = after.strip()
            target = self._resolve_object(session, direct_text, "turn")
            tool = self._resolve_object(session, tool_text, "turn") if tool_text else None
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {direct_text} here." if direct_text else "Turn what?"
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            reply, flags, object_locations = self._turn_response(session, target, tool)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"light", "burn", "extinguish", "on", "off"}:
            action = "off" if head_raw in {"extinguish", "off"} else "on"
            target_text = raw_target or ("lamp" if head_raw != "burn" else "")
            target = self._resolve_object(session, target_text, head_raw)
            if not target:
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                reply = f"You don't see any {target_text} here." if raw_target else ("Burn what?" if head_raw == "burn" else ("Light what?" if action == "on" else "Extinguish what?"))
                return BotAppResult(handled=True, reply_text=reply, command_name=self.SPEC.name)
            if head_raw == "burn" and target == "BODIE":
                self._sessions.pop(peer_id, None)
                return BotAppResult(
                    handled=True,
                    reply_text=self._compact(self._guardian_of_the_dungeon_death()),
                    command_name=self.SPEC.name,
                )
            if target == "FUSE" and action == "on":
                reply, flags, object_locations = self._light_fuse_response(session)
                self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
                return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)
            reply, flags = self._light_action_response(session, target, action)
            if room_id == "BOOM":
                boom_ghost = self._ephemeral_session(
                    session,
                    room_id=room_id,
                    inventory=inventory,
                    flags=flags,
                    object_locations=object_locations,
                )
                if self._open_flame_present(boom_ghost):
                    self._sessions.pop(peer_id, None)
                    return BotAppResult(
                        handled=True,
                        reply_text=self._compact(
                            "Oh dear. It appears that the smell coming from this room was coal gas. "
                            "Carrying an open flame in here was a catastrophically bad plan. "
                            "BOOOOOOOOOOOM. zork: session ended. Send 'zork' to start again."
                        ),
                        command_name=self.SPEC.name,
                    )
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw == "pray":
            reply, new_room, flags, object_locations = self._prayer_response(session, now_unix)
            room_after = new_room or room_id
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {suffix}"), command_name=self.SPEC.name)

        if head_raw == "exorcise":
            reply, flags, object_locations, ended = self._exorcise_response(session)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        if head_raw in {"well", "sinbad", "geronimo"}:
            reply, new_room, flags, object_locations, ended = self._magic_word_response(session, head_raw)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            room_after = new_room or room_id
            suffix = self._room_summary_for_state(
                session,
                room_id=room_after,
                inventory=inventory,
                flags=flags,
                object_locations=object_locations,
            )
            self._write_session_state(session, room_id=room_after, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(
                handled=True,
                reply_text=self._compact(f"{reply} {suffix}"),
                command_name=self.SPEC.name,
            )

        if head_raw in {"attack", "fight", "kill"}:
            target = self._resolve_object(session, raw_target, "attack") if raw_target else None
            reply, flags, object_locations, ended = self._attack_response(session, target)
            if ended:
                self._sessions.pop(peer_id, None)
                return BotAppResult(handled=True, reply_text=self._compact(reply), command_name=self.SPEC.name)
            self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
            return BotAppResult(handled=True, reply_text=self._compact(f"{reply} {self._room_summary(session, room_id)}"), command_name=self.SPEC.name)

        self._write_session_state(session, room_id=room_id, inventory=inventory, flags=flags, object_locations=object_locations, now_unix=now_unix)
        return BotAppResult(handled=True, reply_text="zork: unknown action. Try 'help'.", command_name=self.SPEC.name)
