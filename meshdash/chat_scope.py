"""Chat scope helpers.

The UI groups chat by *scope* (roughly "Everyone" vs direct peer-to-peer).

Rooms will extend this concept later (e.g. "room:retro").
Keeping the server-side scope calculation in one place prevents future drift.
"""

from __future__ import annotations


def chat_scope_for_destination(to_id: object) -> str:
    """Return a stable scope key for a Meshtastic destination.

    Current scopes:
      - "all": broadcast room (^all)
      - "direct": anything else

    Future scopes (planned):
      - "room:<id>" for Meshyface rooms

    The function is intentionally permissive: unknown inputs fall back to "all".
    """

    dest = str(to_id or "").strip()
    if not dest:
        return "all"

    lowered = dest.lower()
    if lowered in (
        "^all",
        "all",
        "broadcast",
        "!ffffffff",
        "ffffffff",
        "0xffffffff",
        "4294967295",
    ):
        return "all"

    return "direct"
