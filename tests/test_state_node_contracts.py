from meshdash.state_node_contracts import CollectedNodes, coerce_collected_nodes


def test_coerce_collected_nodes_passthrough_for_typed_contract():
    typed = CollectedNodes(
        rows=[{"id": "!a"}],
        full=[{"id": "!a", "info": {}}],
        by_id={"!a": {"id": "!a"}},
        with_position_count=1,
    )
    out = coerce_collected_nodes(typed)
    assert out is typed


def test_coerce_collected_nodes_accepts_legacy_mapping_shape():
    out = coerce_collected_nodes(
        {
            "rows": [{"id": "!a"}],
            "full": [{"id": "!a", "info": {}}],
            "by_id": {"!a": {"id": "!a"}},
            "with_position_count": 1,
        }
    )
    assert isinstance(out, CollectedNodes)
    assert out.rows[0]["id"] == "!a"
    assert out.full[0]["id"] == "!a"
    assert out.by_id["!a"]["id"] == "!a"
    assert out.with_position_count == 1
