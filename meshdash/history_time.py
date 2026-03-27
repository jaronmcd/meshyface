import time

from .helpers import to_int as _to_int

_MAX_FUTURE_TIMESTAMP_SKEW_SECONDS = 5 * 60


def normalize_unix_seconds(value: object) -> int | None:
    parsed = _to_int(value)
    if parsed is None or parsed <= 0:
        return None
    if parsed > 10**12:
        parsed //= 1000
    return parsed if parsed > 0 else None


def latest_unix(*values: object) -> int:
    latest = 0
    for value in values:
        parsed = normalize_unix_seconds(value)
        if parsed is not None and parsed > latest:
            latest = parsed
    return latest


def clamp_future_unix(
    value: object,
    *,
    now_unix: int | None = None,
    fallback_unix: object = None,
    max_future_skew_seconds: int = _MAX_FUTURE_TIMESTAMP_SKEW_SECONDS,
    default_to_now: bool = True,
) -> int:
    if now_unix is None:
        now_unix = int(time.time())
    else:
        now_unix = int(now_unix)

    parsed = normalize_unix_seconds(value)
    fallback = normalize_unix_seconds(fallback_unix)
    if parsed is None:
        if fallback is not None:
            return fallback
        if not default_to_now:
            return 0
        return now_unix

    max_allowed = now_unix + max(0, int(max_future_skew_seconds))
    if parsed > max_allowed:
        if fallback is not None and fallback <= max_allowed:
            return fallback
        if not default_to_now:
            return 0
        return now_unix
    return parsed
