GAME_PROTOCOL_PREFIXES = ("rv1|", "ck1|", "ch1|")


def is_game_protocol_text(text: object) -> bool:
    if not isinstance(text, str):
        return False
    raw = text.strip().lower()
    return bool(raw) and raw.startswith(GAME_PROTOCOL_PREFIXES)


def is_game_protocol_chat_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_game_protocol_text(entry.get("text"))
