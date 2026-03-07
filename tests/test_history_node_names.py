from meshdash.history_node_names import build_name_history_points


def test_build_name_history_points_extracts_changes_in_time_order():
    packet_rows = [
        (
            300,
            '{"from":"!abcd1234","to":"^all","rx_time_unix":300,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":300,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!abcd1234","shortName":"N2","longName":"Node Two"}}}',
        ),
        (
            270,
            '{"from":"!abcd1234","to":"^all","rx_time_unix":270,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":270,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!abcd1234","shortName":"N1","longName":"Node One"}}}',
        ),
        (
            260,
            '{"from":"!abcd1234","to":"^all","rx_time_unix":260,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":260,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!eeff0011","shortName":"Other","longName":"Other Node"}}}',
        ),
        (
            250,
            '{"from":"!abcd1234","to":"^all","rx_time_unix":250,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!abcd1234","rxTime":250,"decoded":{"portnum":"NODEINFO_APP","user":{"id":"!abcd1234","shortName":"N1","longName":"Node One"}}}',
        ),
    ]

    history = build_name_history_points(node_id="!ABCD1234", packet_rows=packet_rows)
    assert [entry["time_unix"] for entry in history] == [250, 300]
    assert [entry["short_name"] for entry in history] == ["N1", "N2"]
    assert [entry["long_name"] for entry in history] == ["Node One", "Node Two"]


def test_build_name_history_points_merges_partial_updates_from_sender():
    packet_rows = [
        (
            100,
            '{"from":"!a1b2c3d4","to":"^all","rx_time_unix":100,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!a1b2c3d4","rxTime":100,"decoded":{"portnum":"NODEINFO_APP","user":{"shortName":"AA"}}}',
        ),
        (
            120,
            '{"from":"!a1b2c3d4","to":"^all","rx_time_unix":120,"portnum":"NODEINFO_APP"}',
            '{"fromId":"!a1b2c3d4","rxTime":120,"decoded":{"portnum":"NODEINFO_APP","user":{"longName":"Alpha Alpha"}}}',
        ),
    ]

    history = build_name_history_points(node_id="!a1b2c3d4", packet_rows=packet_rows)
    assert len(history) == 2
    assert history[0]["short_name"] == "AA"
    assert history[0]["long_name"] == ""
    assert history[1]["short_name"] == "AA"
    assert history[1]["long_name"] == "Alpha Alpha"
