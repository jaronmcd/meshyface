"""Shared sampling cadence helpers for summary history metrics."""

_SUMMARY_METRICS_BUCKET_SECONDS = 15


def summary_metrics_bucket_seconds() -> int:
    raw_seconds = int(_SUMMARY_METRICS_BUCKET_SECONDS)
    return max(1, min(3600, raw_seconds))


def summary_metrics_bucket_unix(epoch_seconds: int) -> int:
    bucket_seconds = summary_metrics_bucket_seconds()
    epoch = int(epoch_seconds)
    return epoch - (epoch % bucket_seconds)


def summary_metrics_points_per_hour() -> int:
    bucket_seconds = summary_metrics_bucket_seconds()
    # Integer ceil for 3600 / bucket_seconds.
    return max(1, (3600 + bucket_seconds - 1) // bucket_seconds)


def summary_metrics_query_limit(window_hours: int) -> int:
    hours = max(1, min(24 * 365, int(window_hours)))
    points_per_hour = summary_metrics_points_per_hour()
    max_points = 24 * 365 * points_per_hour
    return max(points_per_hour, min(max_points, (hours * points_per_hour) + 5))
