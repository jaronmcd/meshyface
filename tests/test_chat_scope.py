from meshdash.chat_scope import chat_scope_for_destination


def test_chat_scope_for_destination_defaults_to_all_for_empty_values():
    assert chat_scope_for_destination(None) == "all"
    assert chat_scope_for_destination("") == "all"
    assert chat_scope_for_destination("   ") == "all"


def test_chat_scope_for_destination_recognizes_broadcast_aliases():
    assert chat_scope_for_destination("^all") == "all"
    assert chat_scope_for_destination("ALL") == "all"
    assert chat_scope_for_destination("broadcast") == "all"
    assert chat_scope_for_destination("!FFFFFFFF") == "all"
    assert chat_scope_for_destination("ffffffff") == "all"
    assert chat_scope_for_destination("0xFFFFFFFF") == "all"
    assert chat_scope_for_destination("4294967295") == "all"


def test_chat_scope_for_destination_marks_non_broadcast_as_direct():
    assert chat_scope_for_destination("!abcdef12") == "direct"
    assert chat_scope_for_destination(123) == "direct"
