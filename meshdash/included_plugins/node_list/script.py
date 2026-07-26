"""Plugin-owned node-list fields for the dashboard roster."""

from __future__ import annotations

from meshdash.plugins import Script


script = Script(id="node_list", name="Node List Fields", version="1.0.0")

script.node_field(
    "id",
    label="ID",
    group="Node List",
    value_type="text",
    render_kinds=("text", "chip"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "snr",
    label="SNR",
    group="Node List",
    value_type="number",
    render_kinds=("text", "chip", "metric", "bar"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
    roster_line=1,
)
script.node_field(
    "hardware",
    label="HW",
    group="Node List",
    value_type="text",
    render_kinds=("text", "chip", "badge"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "battery",
    label="Battery",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "pill", "chip", "metric", "bar"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "hops",
    label="Hops",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "pill", "chip", "metric"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
    roster_line=1,
)
script.node_field(
    "last_heard",
    label="Last Heard",
    group="Node List",
    value_type="timestamp",
    render_kinds=("text", "timestamp", "chip"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
    roster_line=1,
)
script.node_field(
    "links",
    label="Links",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "chip", "metric"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "saved",
    label="Total Packets",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "chip", "metric"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "pos",
    label="Pos",
    group="Node List",
    value_type="text",
    render_kinds=("text", "chip"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "location_points",
    label="Location Points",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "chip", "metric"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
)
script.node_field(
    "city",
    label="City",
    group="Node List",
    value_type="text",
    render_kinds=("text", "chip"),
    default_render_kind="text",
    default_visible=False,
    sortable=True,
    roster_line=1,
)
