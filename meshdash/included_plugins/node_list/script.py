"""Plugin-owned node-list fields for the dashboard roster."""

from __future__ import annotations

import re
from collections.abc import Mapping

from meshdash.plugins import Script


script = Script(id="node_list", name="Node List Fields", version="1.0.0")

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
)


_NODE_ID_RE = re.compile(r"![0-9a-f]{8}\Z")
_RESERVED_NODE_IDS = {"!00000000", "!ffffffff"}
_STARTUP_NODE_LIMIT = 16


def _canonical_node_id(value):
    clean = str(value or "").strip().lower()
    if _NODE_ID_RE.fullmatch(clean) is None or clean in _RESERVED_NODE_IDS:
        return ""
    return clean


def _first_present(row, *keys):
    if not isinstance(row, Mapping):
        return None
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _integer(value):
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number


def _timestamp(value):
    number = _integer(value)
    if number is None or number <= 0:
        return None
    return number


def _node_id_from_row(row):
    if not isinstance(row, Mapping):
        return ""
    return _canonical_node_id(_first_present(row, "id", "node_id"))


def _publish_node(ctx, node_id, node):
    clean_node_id = _canonical_node_id(node_id)
    if not clean_node_id:
        return
    safe_node = node if isinstance(node, Mapping) else {}
    hardware = str(_first_present(safe_node, "hardware_model", "hardware") or "").strip() or "n/a"
    ctx.set_node_field(
        clean_node_id,
        "hardware",
        value=hardware,
        sort=hardware.casefold(),
        title=f"Hardware: {hardware}",
    )

    battery = _integer(_first_present(safe_node, "battery_level", "battery"))
    battery_value = battery if battery is not None else "n/a"
    ctx.set_node_field(
        clean_node_id,
        "battery",
        value=battery_value,
        sort=battery,
        title=f"Battery: {battery_value}{'%' if battery is not None else ''}",
    )

    hops = _integer(_first_present(safe_node, "hops_away", "hops"))
    if hops is None:
        hops = _integer(getattr(ctx.message, "hops", None))
    hops_value = hops if hops is not None else "n/a"
    ctx.set_node_field(
        clean_node_id,
        "hops",
        value=hops_value,
        sort=hops,
        title=f"Hops: {hops_value}",
    )

    last_heard = _timestamp(
        _first_present(safe_node, "last_heard_unix", "last_heard_epoch", "last_heard")
    )
    if last_heard is None:
        last_heard = _timestamp(getattr(ctx.message, "received_at", None))
    last_heard_value = last_heard if last_heard is not None else "n/a"
    ctx.set_node_field(
        clean_node_id,
        "last_heard",
        value=last_heard_value,
        sort=last_heard,
        title="Last heard",
    )


@script.on_start
def publish_initial_fields(ctx):
    count = 0
    for node in ctx.mesh.list_nodes():
        if count >= _STARTUP_NODE_LIMIT:
            break
        node_id = _node_id_from_row(node)
        if not node_id:
            continue
        _publish_node(ctx, node_id, node)
        count += 1


@script.on_packet
def publish_sender_fields(ctx):
    node_id = _canonical_node_id(ctx.message.sender_id)
    if not node_id:
        return
    node = ctx.mesh.get_node(node_id) or {}
    _publish_node(ctx, node_id, node)
