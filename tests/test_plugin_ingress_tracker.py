from meshdash.tracker_runtime_impl import DashboardTracker


def test_plugin_listener_runs_only_after_tracker_replay_acceptance() -> None:
    tracker = DashboardTracker(packet_limit=10, history_store=None)
    tracker._record_packet_unlocked = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    accepted: list[int] = []
    tracker.add_accepted_packet_listener(
        lambda packet, _interface: accepted.append(int(packet["id"]))
    )
    packet = {
        "from": 1,
        "to": 2,
        "id": 44,
        "channel": 0,
        "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "!echo"},
    }

    tracker.on_receive(packet, object())
    tracker.on_receive(dict(packet), object())

    assert accepted == [44]


def test_plugin_listener_failure_does_not_break_radio_ingress() -> None:
    tracker = DashboardTracker(packet_limit=10, history_store=None)
    recorded: list[int] = []
    tracker._record_packet_unlocked = (  # type: ignore[method-assign]
        lambda packet, _interface, include_live_count: recorded.append(int(packet["id"]))
    )

    def _broken_listener(_packet: object, _interface: object) -> None:
        raise RuntimeError("listener failed")

    tracker.add_accepted_packet_listener(_broken_listener)
    tracker.on_receive(
        {
            "from": 1,
            "to": 2,
            "id": 45,
            "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hello"},
        },
        object(),
    )
    assert recorded == [45]
