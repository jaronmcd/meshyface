from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

from meshdash.plugins import Script, parse_manifest, validate_script_against_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_LIST_PLUGIN = REPO_ROOT / "meshdash" / "included_plugins" / "node_list"


class _Mesh:
    def __init__(self, nodes):
        self._nodes = tuple(dict(node) for node in nodes)

    def list_nodes(self):
        return self._nodes

    def get_node(self, node_id):
        clean = str(node_id or "").strip().lower()
        for node in self._nodes:
            if str(node.get("id") or "").strip().lower() == clean:
                return dict(node)
        return None


def _context(nodes, *, sender_id="!01020304", hops=3, received_at=1_700_000_000):
    fields = []
    return SimpleNamespace(
        message=SimpleNamespace(
            sender_id=sender_id,
            hops=hops,
            received_at=received_at,
        ),
        mesh=_Mesh(nodes),
        set_node_field=lambda node_id, field_id, **values: fields.append(
            {"node_id": node_id, "field_id": field_id, **values}
        ),
        fields=fields,
    )


def _load_script():
    manifest = parse_manifest(NODE_LIST_PLUGIN / "plugin.toml", source="included")
    namespace = runpy.run_path(str(manifest.entrypoint_path))
    script = namespace[manifest.entrypoint_object]
    return manifest, script


def test_node_list_plugin_declares_node_fields() -> None:
    manifest, script = _load_script()

    assert isinstance(script, Script)
    assert validate_script_against_manifest(manifest, script) is script
    assert manifest.id == "node_list"
    assert manifest.commands == ()
    assert manifest.default_enabled is False
    assert tuple(script.node_fields) == ("hardware", "battery", "hops", "last_heard")
    assert all(field.default_render_kind == "text" for field in script.node_fields.values())
    assert script.node_fields["hardware"].roster_line == 2
    assert script.node_fields["battery"].roster_line == 2
    assert script.node_fields["hops"].roster_line == 1
    assert script.node_fields["last_heard"].roster_line == 1
    assert script.node_fields["hardware"].render_kinds == ("text", "chip", "badge")
    assert script.node_fields["battery"].render_kinds == (
        "text",
        "pill",
        "chip",
        "metric",
        "bar",
    )
    assert script.node_fields["hops"].render_kinds == ("text", "pill", "chip", "metric")
    assert script.node_fields["last_heard"].render_kinds == ("text", "timestamp", "chip")


def test_node_list_plugin_publishes_initial_node_fields() -> None:
    _manifest, script = _load_script()
    context = _context(
        [
            {
                "id": "!01020304",
                "hardware_model": "T-Echo",
                "battery_level": 91,
                "hops_away": 2,
                "last_heard_unix": 1_700_000_100,
            }
        ]
    )

    script.start_handler(context)

    assert context.fields == [
        {
            "node_id": "!01020304",
            "field_id": "hardware",
            "value": "T-Echo",
            "sort": "t-echo",
            "title": "Hardware: T-Echo",
        },
        {
            "node_id": "!01020304",
            "field_id": "battery",
            "value": 91,
            "sort": 91,
            "title": "Battery: 91%",
        },
        {
            "node_id": "!01020304",
            "field_id": "hops",
            "value": 2,
            "sort": 2,
            "title": "Hops: 2",
        },
        {
            "node_id": "!01020304",
            "field_id": "last_heard",
            "value": 1_700_000_100,
            "sort": 1_700_000_100,
            "title": "Last heard",
        },
    ]


def test_node_list_plugin_updates_packet_sender_from_message_fallbacks() -> None:
    _manifest, script = _load_script()
    context = _context(
        [{"id": "!01020304", "hardware": "RAK", "battery": ""}],
        hops=4,
        received_at=1_700_000_200,
    )

    script.packet_handler(context)

    assert context.fields == [
        {
            "node_id": "!01020304",
            "field_id": "hardware",
            "value": "RAK",
            "sort": "rak",
            "title": "Hardware: RAK",
        },
        {
            "node_id": "!01020304",
            "field_id": "battery",
            "value": "n/a",
            "sort": None,
            "title": "Battery: n/a",
        },
        {
            "node_id": "!01020304",
            "field_id": "hops",
            "value": 4,
            "sort": 4,
            "title": "Hops: 4",
        },
        {
            "node_id": "!01020304",
            "field_id": "last_heard",
            "value": 1_700_000_200,
            "sort": 1_700_000_200,
            "title": "Last heard",
        },
    ]
