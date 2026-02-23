from typing import Any, Callable, Dict, Optional


def empty_node_history(node_id: str) -> Dict[str, Any]:
    return {"node_id": str(node_id or ""), "points": [], "positions": [], "summary": {}}


def empty_online_activity(window_hours: int) -> Dict[str, Any]:
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


def build_node_history_loader(
    history_store: Any,
    *,
    default_hours: int,
    default_points: int,
) -> Callable[[str, Optional[int], Optional[int]], Dict[str, Any]]:
    def node_history_loader(
        node_id: str,
        hours_override: Optional[int] = None,
        points_override: Optional[int] = None,
    ) -> Dict[str, Any]:
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
        return history_store.load_node_history(
            node_id=clean_node_id,
            window_hours=hours,
            max_points=points,
        )

    return node_history_loader


def build_online_activity_loader(
    history_store: Any,
    *,
    default_hours: int,
) -> Callable[[Optional[int]], Dict[str, Any]]:
    def online_activity_loader(hours_override: Optional[int] = None) -> Dict[str, Any]:
        hours = (
            hours_override
            if isinstance(hours_override, int) and hours_override > 0
            else int(default_hours)
        )
        if history_store is None:
            return empty_online_activity(hours)
        return history_store.load_online_activity(window_hours=hours)

    return online_activity_loader
