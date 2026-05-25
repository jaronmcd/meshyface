import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.state_node_rows import collect_nodes_rows_typed, collect_nodes_typed


class _Iface:
    def __init__(self) -> None:
        self.nodesByNum = {
            1: {
                "num": 1,
                "user": {"id": "!00000001", "shortName": "A"},
                "isFavorite": True,
            },
            2: {
                "num": 2,
                "user": {"id": "!00000002", "shortName": "B"},
                "isFavorite": False,
            },
            3: {
                "num": 3,
                "user": {"id": "!00000003", "shortName": "C"},
                "is_favorite": "true",
            },
        }


def _rows_by_id(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(row.get("id")): row for row in rows}


def test_collect_nodes_typed_includes_meshtastic_favorite_flag() -> None:
    rows = collect_nodes_typed(_Iface()).rows
    by_id = _rows_by_id(rows)

    assert by_id["!00000001"]["is_favorite"] is True
    assert by_id["!00000002"]["is_favorite"] is False
    assert by_id["!00000003"]["is_favorite"] is True


def test_collect_nodes_rows_typed_includes_meshtastic_favorite_flag() -> None:
    rows = collect_nodes_rows_typed(_Iface()).rows
    by_id = _rows_by_id(rows)

    assert by_id["!00000001"]["is_favorite"] is True
    assert by_id["!00000002"]["is_favorite"] is False
    assert by_id["!00000003"]["is_favorite"] is True
