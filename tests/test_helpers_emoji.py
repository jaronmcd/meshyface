from meshdash.helpers_emoji import (
    emoji_codepoint_from_any,
    emoji_from_codepoint,
    normalize_single_emoji,
)


def test_emoji_from_codepoint_handles_valid_and_invalid_values():
    assert emoji_from_codepoint(0x1F600) == "😀"
    assert emoji_from_codepoint("128077") == "👍"
    assert emoji_from_codepoint(0) is None
    assert emoji_from_codepoint(-1) is None
    assert emoji_from_codepoint(0x110000) is None


def test_emoji_codepoint_from_any_supports_numbers_hex_and_chars():
    assert emoji_codepoint_from_any(128512) == 128512
    assert emoji_codepoint_from_any("128077") == 128077
    assert emoji_codepoint_from_any("U+1F600") == 0x1F600
    assert emoji_codepoint_from_any("1f44d") == 0x1F44D
    assert emoji_codepoint_from_any("😀") == 0x1F600
    assert emoji_codepoint_from_any("\ufe0f👍") == 0x1F44D


def test_emoji_codepoint_from_any_rejects_empty_or_invalid_values():
    assert emoji_codepoint_from_any(None) is None
    assert emoji_codepoint_from_any("") is None
    assert emoji_codepoint_from_any("   ") is None
    assert emoji_codepoint_from_any("0") is None
    assert emoji_codepoint_from_any("U+0000") is None
    assert emoji_codepoint_from_any(object()) is None


def test_normalize_single_emoji_returns_pair_or_none_tuple():
    assert normalize_single_emoji("U+1F44D") == ("👍", 0x1F44D)
    assert normalize_single_emoji("bad input") == (None, None)
    assert normalize_single_emoji("9️⃣") == (None, None)
    assert normalize_single_emoji("👍🏻") == (None, None)
    assert normalize_single_emoji("") == (None, None)
    assert normalize_single_emoji(0) == (None, None)
