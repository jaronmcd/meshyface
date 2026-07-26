from __future__ import annotations

import runpy
from pathlib import Path

from meshdash.plugins import Script, parse_manifest, validate_script_against_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_LIST_PLUGIN = REPO_ROOT / "meshdash" / "included_plugins" / "node_list"


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
    assert tuple(script.node_fields) == (
        "id",
        "snr",
        "hardware",
        "battery",
        "hops",
        "last_heard",
        "links",
        "saved",
        "pos",
        "location_points",
        "city",
    )
    assert script.node_fields["hardware"].roster_line == 2
    assert script.node_fields["battery"].roster_line == 2
    assert script.node_fields["hops"].roster_line == 1
    assert script.node_fields["last_heard"].roster_line == 1
    assert script.node_fields["snr"].roster_line == 1
    assert script.node_fields["city"].roster_line == 1
    assert all(field.default_render_kind == "text" for field in script.node_fields.values())
    assert script.node_fields["saved"].label == "Total Packets"
    assert script.node_fields["location_points"].label == "Location Points"
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
    assert script.node_fields["city"].render_kinds == ("text", "chip")
    assert script.start_handler is None
    assert script.packet_handler is None
