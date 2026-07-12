from typing import Optional

from .helpers import to_float as _to_float


def merge_metric(
    sum_value: object,
    count_value: object,
    min_value: object,
    max_value: object,
    sample: Optional[float],
) -> tuple[float, int, Optional[float], Optional[float]]:
    merged_sum = _to_float(sum_value)
    try:
        merged_count = max(0, int(count_value or 0))
    except (TypeError, ValueError, OverflowError):
        merged_count = 0
    merged_min = _to_float(min_value)
    merged_max = _to_float(max_value)
    if merged_sum is None:
        merged_sum = 0.0
        merged_count = 0
        merged_min = None
        merged_max = None

    clean_sample = _to_float(sample)
    if clean_sample is None:
        return merged_sum, merged_count, merged_min, merged_max

    clean_sum = _to_float(merged_sum + clean_sample)
    if clean_sum is None:
        return merged_sum, merged_count, merged_min, merged_max
    merged_sum = clean_sum
    merged_count += 1
    merged_min = clean_sample if merged_min is None else min(merged_min, clean_sample)
    merged_max = clean_sample if merged_max is None else max(merged_max, clean_sample)
    return merged_sum, merged_count, merged_min, merged_max


def bucket_minute(epoch_seconds: int) -> int:
    return int(epoch_seconds) - (int(epoch_seconds) % 60)


def clean_node_id(node_id: object) -> Optional[str]:
    value = str(node_id or "").strip()
    if not value or value in ("Unknown", "n/a", "^all"):
        return None
    return value
