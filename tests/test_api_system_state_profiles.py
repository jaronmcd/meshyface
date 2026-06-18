from meshdash.api_system import (
    _fault_etag_marker,
    _inject_faults,
    _lite_state_payload,
    _private_mode_state_payload,
    _query_value,
    _truthy_query_flag,
    handle_state_get,
)


class _Headers:
    def get(self, _key: str):
        return None

    def items(self):
        return []


class _Handler:
    def __init__(self, headers=None) -> None:
        self.headers = headers or _Headers()
        self.status_code = None
        self.sent_headers: list[tuple[str, str]] = []
        self.ended = False

    def send_response(self, code: int) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.sent_headers.append((key, value))

    def end_headers(self) -> None:
        self.ended = True

    def header_dict(self) -> dict[str, str]:
        return dict(self.sent_headers)


class _MappingHeaders(dict):
    pass


def test_state_query_helpers_and_payload_filters() -> None:
    assert _truthy_query_flag("lite=1", "lite") is True
    assert _truthy_query_flag("lite=false", "lite") is False
    assert _truthy_query_flag("lite=", "lite") is False
    assert _truthy_query_flag("%", "lite") is False
    assert _query_value("profile=network-map", "profile") == "network-map"
    assert _query_value("profile=", "profile", "default") == "default"
    assert _query_value("%", "profile", "default") == "default"

    full_payload = {
        "my_info": {"id": "!self"},
        "metadata": {"fw": "x"},
        "local_state": {"foo": "bar"},
        "nodes_full": [{"id": "!node"}],
        "faults": [{"id": "fault"}],
        "traffic": {
            "recent_chat": [{"text": "secret"}],
            "recent_packets": [{"id": 1}],
        },
        "summary": {"node_count": 1},
    }

    lite = _lite_state_payload(full_payload)
    private = _private_mode_state_payload(full_payload)

    assert "my_info" not in lite
    assert "metadata" not in lite
    assert "local_state" not in lite
    assert "nodes_full" not in lite
    assert lite["traffic"]["recent_chat"] == [{"text": "secret"}]

    assert "faults" not in private
    assert private["traffic"]["recent_chat"] == []
    assert private["traffic"]["recent_packets"] == [{"id": 1}]
    assert _lite_state_payload("not-a-dict") == "not-a-dict"
    assert _private_mode_state_payload("not-a-dict") == "not-a-dict"


def test_fault_helpers_inject_rows_and_build_stable_etag_marker() -> None:
    rows = [
        {"id": "1", "created_unix": 10, "source": "runtime", "code": "A"},
        {"id": "2", "created_unix": 20, "source": "radio", "code": "B"},
    ]

    assert _fault_etag_marker(rows) == "2;1|10|runtime|A;2|20|radio|B"
    assert _fault_etag_marker("not-rows") == "0"
    assert _inject_faults({"summary": {}}, state_fn=object(), selected_fn=object(), rows=rows) == {
        "summary": {},
        "faults": rows,
    }
    assert _inject_faults({"summary": {}}, state_fn=object(), selected_fn=object(), rows=[]) == {"summary": {}}
    assert _inject_faults("not-a-dict", state_fn=object(), selected_fn=object(), rows=rows) == "not-a-dict"


def test_handle_state_get_uses_lite_chat_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_chat():
        calls.append("lite_chat")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_chat", state_lite_chat)
    setattr(state_fn, "fault_history_fn", lambda: [])

    written: list[object] = []

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        written.append((status_code, payload_obj, no_store, extra_headers))

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=chat",
        private_mode=False,
    )

    assert calls == ["lite_chat"]
    assert written
    assert written[0][0] == 200


def test_handle_state_get_falls_back_to_lite_when_chat_profile_missing() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=chat",
        private_mode=False,
    )

    assert calls == ["lite"]


def test_handle_state_get_uses_lite_network_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_network():
        calls.append("lite_network")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_network", state_lite_network)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=network",
        private_mode=False,
    )

    assert calls == ["lite_network"]


def test_handle_state_get_uses_lite_network_graph_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_network_graph():
        calls.append("lite_network_graph")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_network_graph", state_lite_network_graph)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=network-graph",
        private_mode=False,
    )

    assert calls == ["lite_network_graph"]


def test_handle_state_get_falls_back_to_network_for_network_graph_profile() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_network():
        calls.append("lite_network")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_network", state_lite_network)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=network-graph",
        private_mode=False,
    )

    assert calls == ["lite_network"]


def test_handle_state_get_uses_lite_network_map_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_network_map():
        calls.append("lite_network_map")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_network_map", state_lite_network_map)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=network-map",
        private_mode=False,
    )

    assert calls == ["lite_network_map"]


def test_handle_state_get_falls_back_to_network_for_network_map_profile() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_network():
        calls.append("lite_network")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_network", state_lite_network)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=network-map",
        private_mode=False,
    )

    assert calls == ["lite_network"]


def test_handle_state_get_uses_lite_status_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_status():
        calls.append("lite_status")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_status", state_lite_status)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=status",
        private_mode=False,
    )

    assert calls == ["lite_status"]


def test_handle_state_get_uses_lite_console_profile_when_requested() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite():
        calls.append("lite")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def state_lite_console():
        calls.append("lite_console")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    setattr(state_fn, "lite", state_lite)
    setattr(state_fn, "lite_console", state_lite_console)
    setattr(state_fn, "fault_history_fn", lambda: [])

    def write_json_response_fn(_handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        return None

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=write_json_response_fn,
        query="lite=1&profile=console",
        private_mode=False,
    )

    assert calls == ["lite_console"]


def test_handle_state_get_returns_304_when_etag_matches_in_headers_get() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def etag() -> str:
        return "state-etag"

    setattr(state_fn, "etag", etag)
    setattr(state_fn, "fault_history_fn", lambda: [])
    handler = _Handler(headers={"If-None-Match": "state-etag"})

    written: list[object] = []

    handle_state_get(
        handler,
        state_fn=state_fn,
        write_json_response_fn=lambda *args, **kwargs: written.append(kwargs),
        query="",
        private_mode=False,
    )

    assert calls == []
    assert written == []
    assert handler.status_code == 304
    assert handler.header_dict() == {
        "Cache-Control": "no-store",
        "ETag": "state-etag",
        "Content-Length": "0",
    }
    assert handler.ended is True


def test_handle_state_get_etag_includes_fault_marker_and_matches_case_insensitive_header() -> None:
    rows = [{"id": "fault-1", "created_unix": 10, "source": "runtime", "code": "boom"}]

    def state_fn():
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def etag() -> str:
        return "state-etag"

    setattr(state_fn, "etag", etag)
    setattr(state_fn, "fault_history_fn", lambda: rows)
    handler = _Handler(headers=_MappingHeaders({"if-none-match": "state-etag|fault:1;fault-1|10|runtime|boom"}))

    written: list[object] = []

    handle_state_get(
        handler,
        state_fn=state_fn,
        write_json_response_fn=lambda *args, **kwargs: written.append(kwargs),
        query="",
        private_mode=False,
    )

    assert handler.status_code == 304
    assert written == []


def test_handle_state_get_injects_faults_filters_private_payload_and_writes_etag() -> None:
    rows = [{"id": "fault-1", "created_unix": 10, "source": "runtime", "code": "boom"}]

    def state_fn():
        return {
            "generated_at": "now",
            "summary": {},
            "faults": [{"id": "old"}],
            "my_info": {"id": "!self"},
            "metadata": {"fw": "x"},
            "local_state": {"foo": "bar"},
            "nodes_full": [{"id": "!node"}],
            "traffic": {
                "recent_chat": [{"text": "secret"}],
                "recent_packets": [{"id": 1}],
            },
        }

    def etag() -> str:
        return "state-etag"

    setattr(state_fn, "etag", etag)
    setattr(state_fn, "fault_history_fn", lambda: rows)
    written: list[dict[str, object]] = []

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=lambda _handler, **kwargs: written.append(kwargs),
        query="lite=1&profile=unknown",
        private_mode=True,
    )

    assert len(written) == 1
    response = written[0]
    payload = response["payload_obj"]
    assert response["status_code"] == 200
    assert response["no_store"] is True
    assert response["extra_headers"] == {"ETag": "state-etag|fault:1;fault-1|10|runtime|boom"}
    assert "faults" not in payload
    assert "my_info" not in payload
    assert "metadata" not in payload
    assert "local_state" not in payload
    assert "nodes_full" not in payload
    assert payload["traffic"]["recent_chat"] == []
    assert payload["traffic"]["recent_packets"] == [{"id": 1}]


def test_handle_state_get_ignores_bad_etag_and_fault_history_helpers() -> None:
    calls: list[str] = []

    def state_fn():
        calls.append("full")
        return {"generated_at": "now", "summary": {}, "traffic": {}}

    def bad_etag() -> str:
        raise RuntimeError("etag failed")

    def bad_fault_history():
        raise RuntimeError("fault history failed")

    setattr(state_fn, "etag", bad_etag)
    setattr(state_fn, "fault_history_fn", bad_fault_history)
    written: list[dict[str, object]] = []

    handle_state_get(
        _Handler(),
        state_fn=state_fn,
        write_json_response_fn=lambda _handler, **kwargs: written.append(kwargs),
        query="lite=0",
        private_mode=False,
    )

    assert calls == ["full"]
    assert written[0]["status_code"] == 200
    assert "extra_headers" not in written[0]
