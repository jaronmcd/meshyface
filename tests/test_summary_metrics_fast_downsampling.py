import json
import random

from meshdash.api_history_summary import build_summary_metrics_response
from meshdash.api_input_history import parse_history_window_request
from meshdash.helpers import to_int
from meshdash.history_summary_analytics import (
    build_downsampled_summary_metrics_payload,
    build_summary_metrics_payload,
)
from meshdash.history_views import empty_summary_metrics


def _random_rows(rng: random.Random) -> tuple[list[tuple], list[tuple]]:
    start = 1_780_000_000 - (1_780_000_000 % 15)
    rows = []
    bucket = start
    for _ in range(rng.randint(0, 2500)):
        bucket += 15 * rng.choice([1, 1, 1, 2, 40])
        width = rng.choice([8, 8, 8, 7, 6, 5, 4])
        values = [bucket] + [rng.choice([rng.randint(0, 3000), -5, None, "12"]) for _ in range(7)]
        rows.append(tuple(values[:width]))
    if rows and rng.random() < 0.2:
        rows.insert(0, (0, 1, 2, 3, 4, 5, 6, 7))
    packet_rows = []
    packet_bucket = start - 15 * rng.randint(0, 200)
    for _ in range(rng.randint(0, 2000)):
        packet_bucket += 15 * rng.choice([0, 1, 1, 3])
        packet_rows.append(
            (
                packet_bucket,
                rng.choice(["chat", "telemetry", "position", "nodeinfo", "encrypted", "weird", "", None]),
                rng.choice([1, 2, 5, 0, -1, "3"]),
            )
        )
    return rows, packet_rows


def _response(query: str, loader) -> dict:
    return build_summary_metrics_response(
        query=query,
        summary_metrics_fn=loader,
        default_node_history_hours=24,
        to_int_fn=to_int,
        parse_history_window_request_fn=parse_history_window_request,
        empty_summary_metrics_fn=empty_summary_metrics,
    )


def test_fast_summary_downsampling_matches_building_every_point_first() -> None:
    # Guard: long windows used to build a dict per 15-second sample (172k for 30 days) and
    # downsample afterwards. The fast path aggregates raw rows first and must stay identical.
    rng = random.Random(20260916)
    for _case in range(15):
        rows, packet_rows = _random_rows(rng)

        def full_loader(hours_override, include_packet_series=True):
            return build_summary_metrics_payload(
                window_hours=hours_override or 24,
                rows=rows,
                packet_type_rows=packet_rows if include_packet_series else [],
                bucket_seconds=15,
            )

        def fast_loader(hours_override, include_packet_series=True, max_points=None):
            if max_points is None:
                return full_loader(hours_override, include_packet_series)
            return build_downsampled_summary_metrics_payload(
                window_hours=hours_override or 24,
                rows=rows,
                packet_type_rows=packet_rows if include_packet_series else [],
                bucket_seconds=15,
                max_points=max_points,
            )

        for query in ("hours=720", "hours=720&packet_series=0", "hours=24&points=64", "hours=24&points=5000", "points=all"):
            expected = _response(query, full_loader)
            actual = _response(query, fast_loader)
            assert json.dumps(actual) == json.dumps(expected), query
