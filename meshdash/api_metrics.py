import time
from collections import deque
from collections.abc import Callable, Mapping
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

    radio_link = summary.get("radio_link")
    if isinstance(radio_link, Mapping):
        direct = _coerce_optional_bool(radio_link.get("connected"))
        if direct is None:
            direct = _coerce_optional_bool(radio_link.get("is_connected"))
        if direct is not None:
            return 1 if direct else 0
        state_hint = str(radio_link.get("state") or radio_link.get("status") or "").strip().lower()
        if state_hint in {"connected", "online", "up", "ok"}:
            return 1
        if state_hint in {"lost", "disconnected", "offline", "down", "connecting"}:
            return 0
        return -1

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
    performance: Mapping[str, object] | None = None,
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
    summary = _state_summary(state_payload)
    known_node_count = _to_int(summary.get("known_node_count"))
    if known_node_count is not None:
        lines.extend(
            [
                "# HELP meshdash_known_node_count Nodes known to the radio interface before the poll node window.",
                "# TYPE meshdash_known_node_count gauge",
                f"meshdash_known_node_count {max(0, int(known_node_count))}",
                "# HELP meshdash_node_window_omitted_count Known nodes omitted from routine polls by the node window.",
                "# TYPE meshdash_node_window_omitted_count gauge",
                f"meshdash_node_window_omitted_count {max(0, int(_to_int(summary.get('node_window_omitted_count')) or 0))}",
            ]
        )
    lines.extend(_performance_metric_lines(performance))
    return "\n".join(lines) + "\n"


def _performance_metric_lines(performance: Mapping[str, object] | None) -> list[str]:
    if not isinstance(performance, Mapping):
        return []
    lines: list[str] = []
    profiles = performance.get("state_profiles")
    if isinstance(profiles, Mapping) and profiles:
        lines.extend(
            [
                "# HELP meshdash_state_responses_total /api/state responses by poll profile and HTTP status.",
                "# TYPE meshdash_state_responses_total counter",
            ]
        )
        for profile, stats in profiles.items():
            totals = stats.get("responses_total") if isinstance(stats, Mapping) else None
            for status, total in (totals or {}).items():
                lines.append(f'meshdash_state_responses_total{{profile="{profile}",status="{status}"}} {int(total)}')
        lines.extend(
            [
                "# HELP meshdash_state_response_ms Server time for recent full /api/state responses.",
                "# TYPE meshdash_state_response_ms gauge",
            ]
        )
        for profile, stats in profiles.items():
            if not isinstance(stats, Mapping):
                continue
            for quantile, key in (("0.5", "full_ms_p50"), ("0.95", "full_ms_p95"), ("1", "full_ms_max")):
                value = stats.get(key)
                if value is not None:
                    lines.append(f'meshdash_state_response_ms{{profile="{profile}",quantile="{quantile}"}} {float(value):.1f}')
        lines.extend(
            [
                "# HELP meshdash_state_body_bytes Uncompressed JSON size of the latest full /api/state response.",
                "# TYPE meshdash_state_body_bytes gauge",
            ]
        )
        for profile, stats in profiles.items():
            value = stats.get("body_bytes_last") if isinstance(stats, Mapping) else None
            if value is not None:
                lines.append(f'meshdash_state_body_bytes{{profile="{profile}"}} {int(value)}')
    process = performance.get("process")
    rss = process.get("rss_bytes") if isinstance(process, Mapping) else None
    if rss is not None:
        lines.extend(
            [
                "# HELP meshdash_process_resident_memory_bytes Dashboard process resident memory.",
                "# TYPE meshdash_process_resident_memory_bytes gauge",
                f"meshdash_process_resident_memory_bytes {int(rss)}",
            ]
        )
    return lines


# Budgets for routine /api/state responses on a small (1 vCPU) host. Exceeding them logs a
# rate-limited warning so a slowdown shows up in the service journal before users report it.
STATE_RESPONSE_BUDGET_MS = 500.0
STATE_BODY_BUDGET_BYTES = 1_500_000
STATE_SAMPLES_PER_PROFILE = 240
STATE_BUDGET_MIN_FULL_SAMPLES = 20
STATE_BUDGET_WARNING_INTERVAL_SECONDS = 15 * 60


def _percentile(sorted_values: list[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int(round(fraction * (len(sorted_values) - 1)))))
    return sorted_values[index]


def _process_memory_bytes() -> dict[str, int | None]:
    rss = None
    peak = None
    try:
        with open("/proc/self/status", encoding="ascii", errors="ignore") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1]) * 1024
                elif line.startswith("VmHWM:"):
                    peak = int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return {"rss_bytes": rss, "peak_rss_bytes": peak}


class DashboardApiMetrics:
    def __init__(
        self,
        *,
        monotonic_fn: Callable[[], float] = time.monotonic,
        log_fn: Callable[[str], None] | None = None,
    ) -> None:
        self._lock = Lock()
        self._state_poll_requests_total = 0
        self._state_poll_errors_total = 0
        self._write_auth_denied_total = 0
        self._private_mode_blocks_total = 0
        self._monotonic_fn = monotonic_fn
        self._log_fn = log_fn if log_fn is not None else (lambda message: print(message, flush=True))
        self._state_samples: dict[str, deque[tuple[int, float, int | None]]] = {}
        self._state_status_totals: dict[tuple[str, int], int] = {}
        self._state_warned_at: dict[tuple[str, str], float] = {}
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

    def record_state_response(
        self,
        *,
        profile: str,
        status_code: int,
        elapsed_ms: float,
        body_bytes: int | None,
    ) -> None:
        clean_profile = str(profile or "unknown")
        warnings: list[str] = []
        with self._lock:
            samples = self._state_samples.get(clean_profile)
            if samples is None:
                samples = deque(maxlen=STATE_SAMPLES_PER_PROFILE)
                self._state_samples[clean_profile] = samples
            samples.append((int(status_code), float(elapsed_ms), body_bytes))
            status_key = (clean_profile, int(status_code))
            self._state_status_totals[status_key] = self._state_status_totals.get(status_key, 0) + 1
            stats = self._state_profile_stats_unlocked(clean_profile)
            now = self._monotonic_fn()
            p95 = stats["full_ms_p95"]
            if (
                stats["full_samples"] >= STATE_BUDGET_MIN_FULL_SAMPLES
                and p95 is not None
                and p95 > STATE_RESPONSE_BUDGET_MS
                and self._should_warn_unlocked(clean_profile, "time", now)
            ):
                warnings.append(
                    f"Performance warning: /api/state profile={clean_profile} p95 response "
                    f"{p95:.0f} ms over the last {stats['full_samples']} full responses "
                    f"exceeds the {STATE_RESPONSE_BUDGET_MS:.0f} ms budget."
                )
            if (
                int(status_code) == 200
                and body_bytes is not None
                and body_bytes > STATE_BODY_BUDGET_BYTES
                and self._should_warn_unlocked(clean_profile, "size", now)
            ):
                warnings.append(
                    f"Performance warning: /api/state profile={clean_profile} body {body_bytes} bytes "
                    f"exceeds the {STATE_BODY_BUDGET_BYTES} byte budget."
                )
        for message in warnings:
            try:
                self._log_fn(message)
            except Exception:
                pass

    def _should_warn_unlocked(self, profile: str, kind: str, now: float) -> bool:
        key = (profile, kind)
        last = self._state_warned_at.get(key)
        if last is not None and (now - last) < STATE_BUDGET_WARNING_INTERVAL_SECONDS:
            return False
        self._state_warned_at[key] = now
        return True

    def _state_profile_stats_unlocked(self, profile: str) -> dict[str, object]:
        samples = list(self._state_samples.get(profile) or ())
        full = [sample for sample in samples if sample[0] == 200]
        full_ms = sorted(sample[1] for sample in full)
        full_bytes = [sample[2] for sample in full if sample[2] is not None]
        not_modified = sum(1 for sample in samples if sample[0] == 304)
        return {
            "samples": len(samples),
            "full_samples": len(full),
            "not_modified_ratio": round(not_modified / len(samples), 3) if samples else None,
            "full_ms_p50": _percentile(full_ms, 0.5),
            "full_ms_p95": _percentile(full_ms, 0.95),
            "full_ms_max": full_ms[-1] if full_ms else None,
            "body_bytes_last": full_bytes[-1] if full_bytes else None,
            "body_bytes_max": max(full_bytes) if full_bytes else None,
        }

    def performance_snapshot(self) -> dict[str, object]:
        with self._lock:
            profiles = {}
            for profile in sorted(self._state_samples):
                stats = self._state_profile_stats_unlocked(profile)
                for key in ("full_ms_p50", "full_ms_p95", "full_ms_max"):
                    if stats[key] is not None:
                        stats[key] = round(float(stats[key]), 1)
                stats["within_budget"] = (
                    (stats["full_ms_p95"] is None or stats["full_ms_p95"] <= STATE_RESPONSE_BUDGET_MS)
                    and (stats["body_bytes_max"] is None or stats["body_bytes_max"] <= STATE_BODY_BUDGET_BYTES)
                )
                stats["responses_total"] = {
                    str(status): total
                    for (total_profile, status), total in sorted(self._state_status_totals.items())
                    if total_profile == profile
                }
                profiles[profile] = stats
        return {
            "state_budget_ms": STATE_RESPONSE_BUDGET_MS,
            "state_body_budget_bytes": STATE_BODY_BUDGET_BYTES,
            "state_profiles": profiles,
            "process": _process_memory_bytes(),
        }
