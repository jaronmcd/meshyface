from collections.abc import Mapping
from threading import Lock

from .helpers import to_int as _to_int
from .nodes import parse_utc_text_to_unix as _parse_utc_text_to_unix_helper


def _state_summary(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        return {}
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        return summary
    return {}


def _state_traffic(payload: object) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        return {}
    traffic = payload.get("traffic")
    if isinstance(traffic, Mapping):
        return traffic
    return {}


def _packet_timestamp_unix(entry: object) -> int | None:
    if not isinstance(entry, Mapping):
        return None
    for key in (
        "rx_time_unix",
        "time_unix",
        "packet_rx_time_unix",
    ):
        value = _to_int(entry.get(key))
        if value is not None and value > 0:
            return int(value)
    for key in (
        "rx_time",
        "captured_at",
        "time",
    ):
        value = _parse_utc_text_to_unix_helper(entry.get(key))
        if value is not None and value > 0:
            return int(value)
    return None


def estimate_packet_rate_per_second(payload: object) -> float:
    traffic = _state_traffic(payload)
    recent_packets = traffic.get("recent_packets")
    if not isinstance(recent_packets, list):
        return 0.0

    timestamps: list[int] = []
    for row in recent_packets:
        ts = _packet_timestamp_unix(row)
        if ts is not None and ts > 0:
            timestamps.append(ts)
    if len(timestamps) < 2:
        return 0.0

    min_ts = min(timestamps)
    max_ts = max(timestamps)
    span_seconds = max_ts - min_ts
    if span_seconds <= 0:
        return float(len(timestamps))
    return max(0.0, float(len(timestamps) - 1) / float(span_seconds))


def derive_node_count(payload: object) -> int:
    summary = _state_summary(payload)
    return max(0, int(_to_int(summary.get("node_count")) or 0))


def derive_live_packet_count(payload: object) -> int:
    summary = _state_summary(payload)
    return max(0, int(_to_int(summary.get("live_packet_count")) or 0))


def _coerce_optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "up", "connected", "online"}:
        return True
    if text in {"0", "false", "no", "off", "down", "disconnected", "offline"}:
        return False
    return None


def derive_radio_link_up(payload: object) -> int:
    summary = _state_summary(payload)
    tracker_error = ""
    if isinstance(payload, Mapping):
        tracker_error = str(payload.get("tracker_error") or "").strip().lower()
    if "radio link lost" in tracker_error:
        return 0

    radio = summary.get("radio_connection")
    if not isinstance(radio, Mapping):
        return -1

    state_hint = str(radio.get("state") or radio.get("status") or "").strip().lower()
    if state_hint in {"connected", "online", "up", "ok"}:
        return 1
    if state_hint in {"lost", "disconnected", "offline", "down", "connecting"}:
        return 0

    direct = _coerce_optional_bool(radio.get("is_connected"))
    if direct is None:
        direct = _coerce_optional_bool(radio.get("connected"))
    if direct is not None:
        return 1 if direct else 0

    seen_false = False
    for key in ("wifi", "ethernet", "bluetooth", "serial"):
        nested = radio.get(key)
        if not isinstance(nested, Mapping):
            continue
        connected = _coerce_optional_bool(nested.get("is_connected"))
        if connected is None:
            connected = _coerce_optional_bool(nested.get("connected"))
        if connected is True:
            return 1
        if connected is False:
            seen_false = True
    if seen_false:
        return 0
    return -1


def build_prometheus_metrics_text(
    *,
    state_payload: object,
    counters: Mapping[str, object] | None,
) -> str:
    packet_rate = estimate_packet_rate_per_second(state_payload)
    node_count = derive_node_count(state_payload)
    live_packet_count = derive_live_packet_count(state_payload)
    radio_link_up = derive_radio_link_up(state_payload)

    counter_map = counters if isinstance(counters, Mapping) else {}
    state_poll_requests_total = max(0, int(_to_int(counter_map.get("state_poll_requests_total")) or 0))
    state_poll_errors_total = max(0, int(_to_int(counter_map.get("state_poll_errors_total")) or 0))
    write_auth_denied_total = max(0, int(_to_int(counter_map.get("write_auth_denied_total")) or 0))
    private_mode_blocks_total = max(0, int(_to_int(counter_map.get("private_mode_blocks_total")) or 0))

    lines = [
        "# HELP meshdash_packet_rate_per_second Estimated inbound packet rate based on recent packets.",
        "# TYPE meshdash_packet_rate_per_second gauge",
        f"meshdash_packet_rate_per_second {packet_rate:.6f}",
        "# HELP meshdash_live_packet_count Total live packets observed since runtime start.",
        "# TYPE meshdash_live_packet_count gauge",
        f"meshdash_live_packet_count {live_packet_count}",
        "# HELP meshdash_node_count Current node count in the dashboard summary.",
        "# TYPE meshdash_node_count gauge",
        f"meshdash_node_count {node_count}",
        "# HELP meshdash_state_poll_requests_total Total /api/state poll requests handled.",
        "# TYPE meshdash_state_poll_requests_total counter",
        f"meshdash_state_poll_requests_total {state_poll_requests_total}",
        "# HELP meshdash_state_poll_errors_total Total /api/state poll requests that failed.",
        "# TYPE meshdash_state_poll_errors_total counter",
        f"meshdash_state_poll_errors_total {state_poll_errors_total}",
        "# HELP meshdash_write_auth_denied_total Total write requests denied by API token auth.",
        "# TYPE meshdash_write_auth_denied_total counter",
        f"meshdash_write_auth_denied_total {write_auth_denied_total}",
        "# HELP meshdash_private_mode_blocks_total Total requests blocked by PRIVATE_MODE.",
        "# TYPE meshdash_private_mode_blocks_total counter",
        f"meshdash_private_mode_blocks_total {private_mode_blocks_total}",
        "# HELP meshdash_radio_link_up Radio link state (1 up, 0 down, -1 unknown).",
        "# TYPE meshdash_radio_link_up gauge",
        f"meshdash_radio_link_up {radio_link_up}",
    ]
    return "\n".join(lines) + "\n"


class DashboardApiMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state_poll_requests_total = 0
        self._state_poll_errors_total = 0
        self._write_auth_denied_total = 0
        self._private_mode_blocks_total = 0

    def record_state_poll_request(self) -> None:
        with self._lock:
            self._state_poll_requests_total += 1

    def record_state_poll_error(self) -> None:
        with self._lock:
            self._state_poll_errors_total += 1

    def record_write_auth_denied(self) -> None:
        with self._lock:
            self._write_auth_denied_total += 1

    def record_private_mode_block(self) -> None:
        with self._lock:
            self._private_mode_blocks_total += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "state_poll_requests_total": self._state_poll_requests_total,
                "state_poll_errors_total": self._state_poll_errors_total,
                "write_auth_denied_total": self._write_auth_denied_total,
                "private_mode_blocks_total": self._private_mode_blocks_total,
            }
