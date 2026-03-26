from meshdash.time_sync import normalize_time_sync_timezone, resolve_time_sync


def test_normalize_time_sync_timezone_handles_common_values():
    assert normalize_time_sync_timezone(None) == "local"
    assert normalize_time_sync_timezone("local") == "local"
    assert normalize_time_sync_timezone("UTC") == "UTC"
    assert normalize_time_sync_timezone("bad/timezone") == "local"


def test_resolve_time_sync_uses_host_clock_when_server_sync_disabled():
    payload = resolve_time_sync(
        use_time_server=False,
        timezone_name="UTC",
        now_fn=lambda: 1_700_000_000.75,
    )
    assert payload["ok"] is True
    assert payload["source"] == "host_clock"
    assert payload["applied_unix"] == 1_700_000_000
    assert payload["offset_seconds"] == 0.0


def test_resolve_time_sync_uses_time_server_when_enabled():
    payload = resolve_time_sync(
        use_time_server=True,
        server="time.cloudflare.com",
        timezone_name="UTC",
        now_fn=lambda: 1_700_000_000.0,
        query_time_server_unix_fn=lambda *_args, **_kwargs: 1_700_000_002.25,
    )
    assert payload["ok"] is True
    assert payload["source"] == "time_server"
    assert payload["server"] == "time.cloudflare.com"
    assert payload["applied_unix"] == 1_700_000_002
    assert payload["offset_seconds"] == 2.25


def test_resolve_time_sync_reports_query_failures():
    payload = resolve_time_sync(
        use_time_server=True,
        server="bad.invalid",
        timezone_name="UTC",
        now_fn=lambda: 1_700_000_000.0,
        query_time_server_unix_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("timeout")
        ),
    )
    assert payload["ok"] is False
    assert payload["source"] == "time_server"
    assert payload["server"] == "bad.invalid"
    assert "timeout" in str(payload.get("error"))

