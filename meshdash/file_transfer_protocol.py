FILE_TRANSFER_PROTOCOL_PREFIX = "MF_FILE_V1|"
_FILE_TRANSFER_FRAME_TYPES = {"M", "C", "A"}


def is_file_transfer_protocol_text(text: object) -> bool:
    if not isinstance(text, str):
        return False
    raw = text.strip()
    if not raw.startswith(FILE_TRANSFER_PROTOCOL_PREFIX):
        return False
    parts = raw.split("|", 3)
    if len(parts) < 3:
        return False
    frame_type = str(parts[1]).strip().upper()
    transfer_id = str(parts[2]).strip()
    return frame_type in _FILE_TRANSFER_FRAME_TYPES and bool(transfer_id)


def is_file_transfer_protocol_chat_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    return is_file_transfer_protocol_text(entry.get("text"))
