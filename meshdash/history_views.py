from typing import Callable, Optional, Protocol

from .history_summary_sampling import (
    summary_metrics_bucket_seconds as _summary_metrics_bucket_seconds,
)


class HistoryViewStore(Protocol):
    def load_node_history(
        self,
        *,
        node_id: str,
        window_hours: int,
        max_points: int,
    ) -> dict[str, object]:
        ...

    def load_online_activity(
        self,
        *,
        window_hours: int,
    ) -> dict[str, object]:
        ...

    def load_summary_metrics(
        self,
        *,
        window_hours: int,
        include_packet_series: bool = True,
    ) -> dict[str, object]:
        ...


def empty_node_history(node_id: str) -> dict[str, object]:
    return {
        "node_id": str(node_id or ""),
        "window_hours": 72,
        "points": [],
        "positions": [],
        "name_history": [],
        "packet_timestamps": [],
        "packet_history": [],
        "packet_series": {
            "available": False,
            "bucket_seconds": 60,
            "order": ["all", "chat", "telemetry", "position", "routing", "nodeinfo", "admin", "encrypted", "other"],
            "series": {
                "all": [],
                "chat": [],
                "telemetry": [],
                "position": [],
                "routing": [],
                "nodeinfo": [],
                "admin": [],
                "encrypted": [],
                "other": [],
            },
        },
        "summary": {},
    }


def empty_online_activity(window_hours: int) -> dict[str, object]:
    clean_hours = int(window_hours) if isinstance(window_hours, int) and window_hours > 0 else 72
    return {
        "window_hours": clean_hours,
        "timezone": "local",
        "timezone_label": "local",
        "points": [],
        "hourly_profile": [
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "avg_online_nodes": None,
                "sample_hours": 0,
                "peak_online_nodes": 0,
            }
            for hour in range(24)
        ],
        "summary": {
            "sample_hours": 0,
            "distinct_nodes": 0,
            "max_online_nodes": 0,
            "avg_online_nodes": None,
            "best_hour": None,
            "best_hour_label": None,
            "best_hour_avg_online_nodes": None,
            "window_start": None,
            "window_end": None,
        },
    }


def empty_summary_metrics(window_hours: int) -> dict[str, object]:
    clean_hours = int(window_hours) if isinstance(window_hours, int) and window_hours > 0 else 72
    return {
        "window_hours": clean_hours,
        "bucket_seconds": max(1, int(_summary_metrics_bucket_seconds())),
        "points": [],
        "packet_series": {
            "available": False,
            "order": ["all", "chat", "telemetry", "position", "routing", "nodeinfo", "admin", "encrypted", "other"],
            "series": {
                "all": [],
                "chat": [],
                "telemetry": [],
                "position": [],
                "routing": [],
                "nodeinfo": [],
                "admin": [],
                "encrypted": [],
                "other": [],
            },
        },
        "summary": {
            "samples": 0,
            "window_start": None,
            "window_end": None,
            "latest": {},
            "delta": {},
        },
    }


def build_node_history_loader(
    history_store: HistoryViewStore | None,
    *,
    default_hours: int,
    default_points: int,
) -> Callable[[str, Optional[int], Optional[int]], dict[str, object]]:
    def node_history_loader(
        node_id: str,
        hours_override: Optional[int] = None,
        points_override: Optional[int] = None,
    ) -> dict[str, object]:
        clean_node_id = str(node_id or "").strip()
        if history_store is None:
            return empty_node_history(clean_node_id)
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        points = (
            points_override
            if isinstance(points_override, int) and points_override > 0
            else int(default_points)
        )
        try:
            return history_store.load_node_history(
                node_id=clean_node_id,
                window_hours=hours,
                max_points=points,
            )
        except Exception:
            return empty_node_history(clean_node_id)

    return node_history_loader


def build_online_activity_loader(
    history_store: HistoryViewStore | None,
    *,
    default_hours: int,
) -> Callable[[Optional[int]], dict[str, object]]:
    def online_activity_loader(hours_override: Optional[int] = None) -> dict[str, object]:
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        if history_store is None:
            return empty_online_activity(hours)
        try:
            return history_store.load_online_activity(window_hours=hours)
        except Exception:
            return empty_online_activity(hours)

    return online_activity_loader


def build_summary_metrics_loader(
    history_store: HistoryViewStore | None,
    *,
    default_hours: int,
) -> Callable[[Optional[int]], dict[str, object]]:
    def summary_metrics_loader(
        hours_override: Optional[int] = None,
        *,
        include_packet_series: bool = True,
    ) -> dict[str, object]:
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        if history_store is None:
            return empty_summary_metrics(hours)
        load_summary_metrics_fn = getattr(history_store, "load_summary_metrics", None)
        if not callable(load_summary_metrics_fn):
            return empty_summary_metrics(hours)
        try:
            return load_summary_metrics_fn(
                window_hours=hours,
                include_packet_series=include_packet_series,
            )
        except Exception:
            return empty_summary_metrics(hours)

    return summary_metrics_loader
