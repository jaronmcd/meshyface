import math
from datetime import datetime, timezone
from typing import Optional


def to_int(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def to_float(value: object) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def format_epoch(epoch_value: object) -> Optional[str]:
    epoch = to_int(epoch_value)
    if epoch is None or epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
