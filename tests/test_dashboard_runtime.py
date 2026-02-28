import argparse

from meshdash.dashboard_runtime import run_dashboard_runtime
from meshdash.revision import RevisionInfo


class _FakeIface:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeHistoryStore:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False

    def close(self):
        self.closed = True


class _FakeTracker:
    def __init__(self, packet_limit, history_store):
        self.packet_limit = packet_limit
        self.history_store = history_store
        self.seeded_packets = []
        self.recorded_chat = []

    def on_receive(self, packet, interface):
        return None

    def has_recent_packets(self):
        return False

    def seed_packet(self, packet, iface):
        self.seeded_packets.append((packet, iface))

    def record_local_chat(self, **kwargs):
        self.recorded_chat.append(kwargs)


class _FakeServer:
    def __init__(self, addr, handler_cls):
        self.addr = addr
        self.handler_cls = handler_cls
        self.server_address = ("127.0.0.1", 8877)
        self.closed = False

    def serve_forever(self, poll_interval=0.5):
        raise KeyboardInterrupt()

    def server_close(self):
        self.closed = True


def test_run_dashboard_runtime_wires_core_dependencies():
    args = argparse.Namespace(
        history_db="/tmp/fake.sqlite3",
        no_history=False,
        seed_from_node_db=True,
        history_max_rows=5000,
        history_retention_days=7,
        history_event_max_rows=200000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        packet_limit=250,
        show_secrets=False,
        node_history_hours=72,
        node_history_max_points=1440,
        refresh_ms=3000,
        http_host="127.0.0.1",
        http_port=8877,
    )

    calls = {
        "subscribe": [],
        "seed": 0,
        "iface": None,
        "history_store": None,
        "server": None,
    }

    def _open_mesh_interface(_args):
        iface = _FakeIface()
        calls["iface"] = iface
        return iface

    def _history_store_cls(**kwargs):
        store = _FakeHistoryStore(**kwargs)
        calls["history_store"] = store
        return store

    def _subscribe(cb, topic):
        calls["subscribe"].append((cb, topic))

    def _seed_tracker(tracker, iface):
        calls["seed"] += 1
        tracker.seed_packet({"id": 1}, iface)

    def _server_cls(addr, handler_cls):
        server = _FakeServer(addr, handler_cls)
        calls["server"] = server
        return server

    run_dashboard_runtime(
        args,
        mesh_target_label_fn=lambda _args: "127.0.0.1:4403 (tcp)",
        open_mesh_interface_fn=_open_mesh_interface,
        history_store_cls=_history_store_cls,
        dashboard_tracker_cls=_FakeTracker,
        subscribe_fn=_subscribe,
        seed_tracker_fn=_seed_tracker,
        revision_info_fn=lambda: RevisionInfo(
            version="0.1.0",
            commit="test",
            label="Rev: v0.1.0 (test)",
            title="Rev",
        ),
        build_state_fn=lambda **kwargs: {"ok": True},
        build_node_history_loader_fn=lambda **kwargs: (lambda *_a, **_k: {}),
        build_online_activity_loader_fn=lambda **kwargs: (lambda *_a, **_k: {}),
        send_chat_message_fn=lambda **kwargs: {"ok": True},
        send_reaction_packet_fn=lambda **kwargs: type("Packet", (), {"id": 1})(),
        get_local_node_id_fn=lambda iface: "!local",
        normalize_single_emoji_fn=lambda value: (None, None),
        to_int_fn=lambda value: int(value) if value is not None else None,
        utc_now_fn=lambda: "2026-02-22T00:00:00Z",
        render_html_fn=lambda **kwargs: "<html></html>",
        make_http_handler_fn=lambda *args, **kwargs: object(),
        guess_lan_ipv4_fn=lambda: "192.168.1.10",
        default_chat_max_bytes=220,
        threading_http_server_cls=_server_cls,
    )

    assert calls["subscribe"]
    assert calls["subscribe"][0][1] == "meshtastic.receive"
    assert calls["seed"] == 1
    assert calls["iface"] is not None and calls["iface"].closed is True
    assert calls["history_store"] is not None and calls["history_store"].closed is True
    assert calls["server"] is not None and calls["server"].closed is True
