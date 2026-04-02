# Multi-Radio V2 Peer Review Handoff (GPT)

Doc status: proposal
Last reviewed: 2026-03-14

Use this for external architecture review of the new V2 direction.

Status (audited 2026-03-14): review prompt/support doc for a proposed V2 architecture; not evidence of implemented V2 runtime behavior in this branch.

## Review Assumption

This is a greenfield V2 plan.

1. Backward compatibility is not required.
2. Legacy migration constraints are not driving decisions.
3. Review should optimize for correctness and long-term architecture quality.

## Files To Share

1. `docs/MULTI_RADIO_INGEST_PLAN.md`
2. This file: `docs/MULTI_RADIO_GPT_REVIEW_HANDOFF.md`
3. Optional repo context:
   - `mesh_connection.py`
   - `meshdash/dashboard_runtime_context.py`
   - `meshdash/tracker_storage.py`
   - `meshdash/history_schema_tables.py`
   - `meshdash/history_writes.py`

## Target Architecture Summary

1. Backend can run dual role:
   - local collector (multi-radio ingest, local DB)
   - uplink contributor (sync canonical events upstream)
2. Optional aggregator backend receives fan-in from many collectors.
3. Canonical event model with per-source observations.
4. Outbox + ACK sync with replay-safe idempotency.
5. Loop prevention by `origin_backend_id` and per-peer delivery guards.
6. Eventual consistency (not strict global ordering).
7. Network-wide contribution model: any reachable radio can feed the shared database path.

## Critical Questions Reviewer Must Answer

1. Is the canonical key strategy robust enough in real RF conditions?
2. Does the schema cleanly separate canonical truth from observations?
3. Is the sync protocol truly idempotent and loop-safe?
4. Are failure and backpressure controls sufficient for production?
5. Is the phased plan implementable without hidden coupling risks?

## Required Output Format

Reviewer response must include:

1. Top risks (ordered high to low, with specific failure scenarios)
2. Data model critique (exact schema/index changes recommended)
3. Dedupe critique (false positives, false negatives, collision paths)
4. Sync protocol critique (ordering, replay, ACK semantics, loop prevention)
5. Operational critique (observability, alerting, runbook gaps)
6. Revised execution plan (practical phase sequence and scope cuts)
7. MVP ship recommendation (`ship`, `ship with conditions`, or `do not ship`)

## Paste-Ready Prompt For GPT

```text
You are performing an architecture peer review for a Python/SQLite Meshtastic backend redesign.

Review docs/MULTI_RADIO_INGEST_PLAN.md with this assumption:
- This is a greenfield V2 architecture.
- Backward compatibility is NOT required.
- Legacy migration constraints are not a design goal.

System intent:
1) Multi-radio ingest on collector backends
2) Canonical event dedupe with per-source observations
3) Dual-role backend capability:
   - local collection into local DB
   - upstream contribution to another backend via outbox sync
4) Optional aggregator backend fan-in
5) Eventual consistency with idempotent replay and loop prevention
6) Network-wide contribution where any reachable radio can contribute via collector/aggregator paths

Your output must include:
1) Top risks ordered by severity, with concrete failure examples
2) Data model critique with precise schema/index recommendations
3) Dedupe-key analysis: collision, false-positive, false-negative risks
4) Sync protocol analysis: replay safety, ACK model, ordering, loop control
5) Operational analysis: backpressure, observability, alerting, recovery
6) A revised phased implementation plan with practical scope boundaries
7) Clear MVP recommendation: ship / ship-with-conditions / no-ship

Be concrete. If you disagree with any part of the plan, propose exact alternatives.
```

## Acceptance Checklist After Review

Proceed only if all are true:

1. Canonical key and dedupe rules are explicit and testable.
2. Canonical-vs-observation write semantics are unambiguous.
3. Sync replay and loop controls are proven by test strategy.
4. Outbox/backpressure behavior is bounded and observable.
5. Phase boundaries are realistic and independently verifiable.
