from meshdash.file_transfer_protocol import (
    is_file_transfer_protocol_chat_entry,
    is_file_transfer_protocol_text,
)


def test_is_file_transfer_protocol_text_matches_supported_frames():
    assert is_file_transfer_protocol_text("MF_FILE_V1|M|abc123|name|64|1")
    assert is_file_transfer_protocol_text("MF_FILE_V1|C|abc123|0|QUJD")
    assert is_file_transfer_protocol_text("MF_FILE_V1|A|abc123|0|1|AA==")


def test_is_file_transfer_protocol_text_rejects_non_protocol_text():
    assert not is_file_transfer_protocol_text("")
    assert not is_file_transfer_protocol_text("hello")
    assert not is_file_transfer_protocol_text("MF_FILE_V1|X|abc123|payload")


def test_is_file_transfer_protocol_chat_entry_checks_text_field():
    assert is_file_transfer_protocol_chat_entry({"text": "MF_FILE_V1|A|abc123|0|1|AA=="})
    assert not is_file_transfer_protocol_chat_entry({"text": "hello"})
    assert not is_file_transfer_protocol_chat_entry({"message_id": 1})
