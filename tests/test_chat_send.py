import pytest

from meshdash.chat_send import (
    build_chat_send_response,
    delivery_state_for_send,
    prepare_chat_send_input,
)


def _to_int(value):
    if value in (None, ""):
        return None
    return int(value)


def test_prepare_chat_send_input_text_path_normalizes_destination_and_channel():
    prepared = prepare_chat_send_input(
        text=" hello ",
        destination="all",
        channel_index=-1,
        reply_id=None,
        retry_of="123",
        emoji=None,
        chat_max_bytes=220,
        normalize_single_emoji_fn=lambda value: (None, None),
        to_int_fn=_to_int,
    )

    assert prepared["text"] == "hello"
    assert prepared["destination"] == "^all"
    assert prepared["channel_index"] == 0
    assert prepared["ack_requested"] is False
    assert prepared["retry_of"] == 123
    assert prepared["is_reaction"] is False


def test_prepare_chat_send_input_reaction_requires_reply_id():
    with pytest.raises(ValueError, match="valid reply_id"):
        prepare_chat_send_input(
            text="",
            destination="!abcd1234",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji="😀",
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: ("😀", ord("😀")),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_non_positive_reply_id():
    with pytest.raises(ValueError, match="positive packet id"):
        prepare_chat_send_input(
            text="hello",
            destination="^all",
            channel_index=0,
            reply_id=0,
            retry_of=None,
            emoji=None,
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: (None, None),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_reaction_with_text():
    with pytest.raises(ValueError, match="must not include text"):
        prepare_chat_send_input(
            text="hello",
            destination="!abcd1234",
            channel_index=0,
            reply_id=123,
            retry_of=None,
            emoji="😀",
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: ("😀", ord("😀")),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_multi_codepoint_reaction_emoji():
    with pytest.raises(ValueError, match="single-codepoint"):
        prepare_chat_send_input(
            text="",
            destination="!abcd1234",
            channel_index=0,
            reply_id=123,
            retry_of=None,
            emoji="9️⃣",
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: (None, None),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_empty_message():
    with pytest.raises(ValueError, match="cannot be empty"):
        prepare_chat_send_input(
            text="   ",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: (None, None),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_too_long_message():
    with pytest.raises(ValueError, match="too long"):
        prepare_chat_send_input(
            text="abcd",
            destination="^all",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
            chat_max_bytes=3,
            normalize_single_emoji_fn=lambda value: (None, None),
            to_int_fn=_to_int,
        )


def test_prepare_chat_send_input_rejects_invalid_destination():
    with pytest.raises(ValueError, match=r"Destination must be '\^all'"):
        prepare_chat_send_input(
            text="hello",
            destination="peer",
            channel_index=0,
            reply_id=None,
            retry_of=None,
            emoji=None,
            chat_max_bytes=220,
            normalize_single_emoji_fn=lambda value: (None, None),
            to_int_fn=_to_int,
        )


def test_delivery_state_for_send_matches_ack_behavior():
    assert delivery_state_for_send(ack_requested=False, sent_packet_id=None) == "sent"
    assert delivery_state_for_send(ack_requested=True, sent_packet_id=123) == "pending"
    assert delivery_state_for_send(ack_requested=True, sent_packet_id=None) == "error"


def test_build_chat_send_response_sets_text_or_reaction_fields():
    text_response = build_chat_send_response(
        now_text_fn=lambda: "2026-02-22T12:00:00Z",
        local_node_id="!me000001",
        destination="!abcd1234",
        channel_index=1,
        message_id=123,
        reply_id=None,
        retry_of=10,
        ack_requested=True,
        delivery_state="pending",
        text="hello",
        is_reaction=False,
        emoji=None,
        emoji_codepoint=None,
    )
    assert text_response["text"] == "hello"
    assert text_response["retry_of"] == 10

    reaction_response = build_chat_send_response(
        now_text_fn=lambda: "2026-02-22T12:00:00Z",
        local_node_id="!me000001",
        destination="!abcd1234",
        channel_index=1,
        message_id=777,
        reply_id=555,
        retry_of=None,
        ack_requested=False,
        delivery_state="sent",
        text="",
        is_reaction=True,
        emoji="😀",
        emoji_codepoint=ord("😀"),
    )
    assert reaction_response["text"] == ""
    assert reaction_response["reaction"] == "😀"
    assert reaction_response["reaction_codepoint"] == ord("😀")
