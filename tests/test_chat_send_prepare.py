import pytest

from meshdash.chat_send_prepare import prepare_chat_send_input
from meshdash.config import DEFAULT_CHAT_MAX_BYTES


def _prepare(text: str) -> dict[str, object]:
    return prepare_chat_send_input(
        text=text,
        destination="^all",
        channel_index=0,
        reply_id=None,
        retry_of=None,
        emoji=None,
        chat_max_bytes=DEFAULT_CHAT_MAX_BYTES,
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda _value: None,
    )


def test_default_chat_limit_is_200_bytes() -> None:
    assert DEFAULT_CHAT_MAX_BYTES == 200


def test_prepare_chat_send_input_allows_200_byte_message() -> None:
    prepared = _prepare("x" * 200)

    assert prepared["text"] == "x" * 200


def test_prepare_chat_send_input_rejects_message_above_200_bytes() -> None:
    with pytest.raises(
        ValueError,
        match=r"Message is too long \(201 bytes\). Limit is 200 bytes\.",
    ):
        _prepare("x" * 201)


def test_prepare_chat_send_input_rejects_local_double_slash_commands() -> None:
    with pytest.raises(
        ValueError,
        match=r"Messages starting with // are local commands and cannot be sent",
    ):
        _prepare("//help")

    with pytest.raises(
        ValueError,
        match=r"Messages starting with // are local commands and cannot be sent",
    ):
        _prepare("   //search node")
