from types import SimpleNamespace

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.dashboard_runner_impl import _build_offline_runtime_context
from meshdash.runtime_lifecycle import close_runtime_resources


class _RevisionInfo:
    version = "0.1.0"
    commit = "test"
    label = "Rev: test"
    title = "Dashboard revision: test"

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "commit": self.commit,
            "label": self.label,
            "title": self.title,
        }


class _CloseRecorder:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.closed = False
        self._error = error

    def close(self) -> None:
        self.closed = True
        if self._error is not None:
            raise self._error


class _ServerRecorder:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.closed = False
        self._error = error

    def server_close(self) -> None:
        self.closed = True
        if self._error is not None:
            raise self._error


def test_close_runtime_resources_ignores_interface_close_errors() -> None:
    server = _ServerRecorder()
    iface = _CloseRecorder(error=BrokenPipeError("radio reset"))
    history_store = _CloseRecorder()

    close_runtime_resources(
        server=server,
        iface=iface,
        history_store=history_store,
    )

    assert server.closed is True
    assert iface.closed is True
    assert history_store.closed is True


def test_close_runtime_resources_continues_after_server_close_error() -> None:
    server = _ServerRecorder(error=OSError("server close failed"))
    iface = _CloseRecorder()
    history_store = _CloseRecorder()

    close_runtime_resources(
        server=server,
        iface=iface,
        history_store=history_store,
    )

    assert server.closed is True
    assert iface.closed is True
    assert history_store.closed is True


def test_offline_runtime_uses_cached_history_nodes(tmp_path) -> None:
    class _HistoryStore:
        def __init__(
            self,
            db_path: str,
            max_rows: int,
            retention_days: int,
            event_max_rows: int,
            event_retention_days: int,
            rollup_retention_days: int,
        ) -> None:
            del max_rows, retention_days, event_max_rows, event_retention_days
            del rollup_retention_days
            self.db_path = db_path

        def load_node_capabilities(self) -> dict[str, dict[str, object]]:
            return {
                "!49b5dff0": {
                    "first_seen_unix": 100,
                    "first_seen": "1970-01-01 00:01:40Z",
                    "last_seen_unix": 200,
                    "last_seen": "1970-01-01 00:03:20Z",
                    "has_position": True,
                    "last_hops": 2,
                    "battery_level": 91,
                    "last_short_name": "grn",
                    "last_long_name": "green",
                },
                "!02edc4f8": {
                    "first_seen_unix": 50,
                    "first_seen": "1970-01-01 00:00:50Z",
                    "last_seen_unix": 150,
                    "last_seen": "1970-01-01 00:02:30Z",
                    "has_position": False,
                    "last_short_name": "chip",
                    "last_long_name": "Chip",
                },
            }

        def load_node_saved_counts(self) -> dict[str, dict[str, object]]:
            return {
                "!49b5dff0": {
                    "saved_packets": 12,
                    "saved_points": 3,
                    "saved_last_seen": "1970-01-01 00:03:20Z",
                }
            }

        def load_node_position_counts(self) -> dict[str, dict[str, object]]:
            return {
                "!49b5dff0": {
                    "position_points": 4,
                    "position_last_seen_unix": 180,
                    "position_last_seen": "1970-01-01 00:03:00Z",
                }
            }

    args = SimpleNamespace(
        history_db=str(tmp_path / "mesh_dashboard_history.sqlite3"),
        no_history=False,
        history_max_rows=1000,
        history_retention_days=7,
        history_event_max_rows=1000,
        history_event_retention_days=30,
        history_rollup_retention_days=365,
        games_enable=False,
    )
    context = _build_offline_runtime_context(
        args,
        startup_error=RuntimeError("waiting for radio link"),
        connecting=True,
        history_store_cls=_HistoryStore,
        mesh_target_label_fn=lambda _args: "/dev/serial0 (serial)",
        revision_info_fn=_RevisionInfo,
        utc_now_fn=lambda: "2026-06-07 21:00:00Z",
    )

    state = context.state_fn()

    assert context.history_enabled is True
    assert state["summary"]["node_count"] == 2
    assert state["summary"]["nodes_with_position"] == 1
    assert state["summary"]["radio_link"]["state"] == "connecting"
    assert state["summary"]["radio_link"]["connected"] is False
    assert state["summary"]["radio_connection"]["state"] == "connecting"
    assert [node["id"] for node in state["nodes"]] == ["!49b5dff0", "!02edc4f8"]
    assert state["nodes"][0]["long_name"] == "green"
    assert state["nodes"][0]["saved_packets"] == 12
    assert state["nodes"][0]["position_points"] == 4
    assert state["nodes"][0]["position_last_seen_unix"] == 180
    assert state["nodes"][0]["hops_away"] == 2
