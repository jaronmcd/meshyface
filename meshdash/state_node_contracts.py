from dataclasses import dataclass
from typing import Any, Mapping

NodeRow = dict[str, Any]
NodeFullRow = dict[str, Any]
NodeByIdMap = dict[str, NodeRow]


@dataclass(frozen=True)
class CollectedNodes:
    rows: list[NodeRow]
    full: list[NodeFullRow]
    by_id: NodeByIdMap
    with_position_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "full": self.full,
            "by_id": self.by_id,
            "with_position_count": self.with_position_count,
        }


def coerce_collected_nodes(value: CollectedNodes | Mapping[str, Any]) -> CollectedNodes:
    if isinstance(value, CollectedNodes):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected CollectedNodes or mapping, got {type(value)!r}")

    rows_raw = value.get("rows") or []
    full_raw = value.get("full") or []
    by_id_raw = value.get("by_id") or {}
    with_position_raw = value.get("with_position_count") or 0

    rows = rows_raw if isinstance(rows_raw, list) else []
    full = full_raw if isinstance(full_raw, list) else []
    by_id = by_id_raw if isinstance(by_id_raw, dict) else {}
    with_position_count = int(with_position_raw)

    return CollectedNodes(
        rows=rows,
        full=full,
        by_id=by_id,
        with_position_count=with_position_count,
    )
