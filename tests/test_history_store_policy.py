from meshdash.history_store_policy import (
    HistoryStorePolicy,
    build_history_store_policy,
    policy_from_store_fields,
)


def test_build_history_store_policy_applies_minimums_and_converts_days():
    policy = build_history_store_policy(
        max_rows=5,
        retention_days=7,
        event_max_rows=50,
        event_retention_days=30,
        rollup_retention_days=365,
    )
    assert isinstance(policy, HistoryStorePolicy)
    assert policy.max_rows == 100
    assert policy.event_max_rows == 1000
    assert policy.retention_seconds == 7 * 86400
    assert policy.event_retention_seconds == 30 * 86400
    assert policy.rollup_retention_seconds == 365 * 86400


def test_policy_from_store_fields_reads_existing_runtime_values():
    store = type(
        "_Store",
        (),
        {
            "max_rows": 5000,
            "event_max_rows": 200000,
            "retention_seconds": 7 * 86400,
            "event_retention_seconds": 30 * 86400,
            "rollup_retention_seconds": 365 * 86400,
        },
    )()
    policy = policy_from_store_fields(store)
    assert policy == HistoryStorePolicy(
        max_rows=5000,
        event_max_rows=200000,
        retention_seconds=7 * 86400,
        event_retention_seconds=30 * 86400,
        rollup_retention_seconds=365 * 86400,
    )
