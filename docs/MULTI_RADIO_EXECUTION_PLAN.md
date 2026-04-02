# Multi-Radio V2 Execution Plan (This Branch)

Doc status: proposal
Last reviewed: 2026-03-14

Status (audited 2026-03-14):

1. Planning document only (V2 proposal).
2. This repository branch does not currently implement the V2 multi-radio schema/sync APIs described below.
3. Original target branch reference (`feat/multi-radio-integration`) is historical context.

Objective:

1. Increase receive coverage with two home radios (attic + ground floor).
2. Build one canonical event stream with per-radio observations.
3. Defer TX strategy and repetition control to a later phase.

## Deep-Dive Outcome From GPT ZIP

Reviewed: `/home/j/Downloads/mesh_py-meshyface-alpha-codex-handoff.zip`

High-confidence findings:

1. ZIP is mostly repo parity plus architecture docs.
2. Most useful artifact was `MULTI_RADIO_V2_CODEX_HANDOFF.md` in the reviewed ZIP (not checked into this repo).
3. Key corrections we must enforce in implementation:
   - Canonical key must not depend on decode-only fields.
   - Sync queue must support typed items (MVP uses `event`; `observation` is post-MVP).
   - Receiver idempotency must key by `sender_backend_id`.
   - ACK must only happen after durable transaction commit.
   - Backpressure must be bounded by policy and metrics.

## Scope

In scope:

1. Multi-source receive ingest (serial + TCP radios).
2. Canonical dedupe plus source-level observation storage.
3. Collector to aggregator sync using durable outbox.
4. Source and sync health API visibility.

Out of scope:

1. TX path arbitration between radios.
2. Transmit repeat suppression.
3. Multi-hop backend forwarding graph.

## Home Topology Target

MVP deployment:

1. One backend process on home server.
2. Two connected radios:
   - attic radio (long range receive bias)
   - ground-floor radio (local receive bias)
3. Optional uplink peer (remote aggregator) after local correctness is proven.

## Non-Negotiable Invariants

1. Same RF packet seen by both radios creates one canonical event.
2. Every source sighting is preserved in observations.
3. Local ingest stays healthy when upstream sync is down.
4. Replay of sync batches is idempotent.
5. No ACK is emitted before canonical/observation writes are committed.

## Data and Identity Model

Canonical key rules:

1. Primary identity uses stable wire fields:
   - `from`/`from_id` (sender)
   - `packet_id` (when `> 0`)
2. Fallback key (for no packet id) excludes observer-local fields:
   - include stable sender + wire payload signature (encrypted payload bytes)
   - exclude RSSI/SNR/hops/time-bucket from identity
3. Persist collision anomalies when same key conflicts on payload hash.

Core tables:

1. `backends`
2. `sources`
3. `events_canonical`
4. `event_observations`
5. `sync_peers`
6. `sync_outbox` (typed items; MVP uses `event`)
7. `sync_inbox_seen`
8. `dedupe_collisions` (anomaly log)

## Execution Sequence (PR-Sized)

## PR 1: Schema Foundation

Deliver:

1. New tables and indexes listed above.
2. Migration entrypoints and idempotent creation.
3. `event_key` builder module with deterministic tests.

Done when:

1. Schema initializes cleanly on empty DB.
2. Re-running init causes no structural drift.

## PR 2: Source Manager Runtime

Deliver:

1. Multi-source connection manager in runtime context.
2. Stable `source_id` mapping (not endpoint-IP identity).
3. Source liveness tracking (`last_seen`, error state).

Done when:

1. Attic and ground-floor radios ingest concurrently for 30+ minutes.
2. Source status endpoint shows both with fresh heartbeat.

## PR 3: Canonical + Observation Writes

Deliver:

1. Ingest pipeline writes canonical first, then observation merge/upsert.
2. Rollups and counts driven only by canonical insert success.
3. Dedupe collision metric + persisted anomaly row.

Done when:

1. Duplicate receptions from both radios produce one canonical row.
2. Observation rows reflect both radios.

## PR 4: Read Model and Dashboard API

Deliver:

1. State/history readers consume canonical + observation structure.
2. API adds source attribution metadata for debugging.
3. Sidebar/source status data is available without blocking map render.

Done when:

1. UI counts are stable under duplicate ingest.
2. Operators can identify which radios contributed.

## PR 5: Sync Outbox Sender

Deliver:

1. Outbox entries for `event` items only (MVP). Observation sync is post-MVP.
2. Retry worker with backoff + jitter.
3. Queue bounds:
   - canonical items never dropped
   - (post-MVP) observation degradation policy under pressure

Done when:

1. Upstream outage does not affect local ingest.
2. Queue drains automatically after upstream recovery.

## PR 6: Sync Receiver Endpoint

Deliver:

1. `POST /sync/v1/events/batch`.
2. Idempotency guard on `(sender_backend_id, item_type, item_key, item_hash)`.
3. Single transaction for apply + inbox mark + ACK response state.

Done when:

1. Replayed batch is acknowledged as duplicate with no mutation.
2. Crash/retry tests show no accepted-data loss.

## PR 7: Hardening and Runbook

Deliver:

1. `/api/sources/status` and `/api/sync/status`.
2. Metrics:
   - ingest rate by source
   - dedupe hit ratio
   - fallback-key rate
   - collision rate
   - outbox depth and max age
3. Operator actions:
   - pause/resume peer
   - force sync retry
   - bounded outbox cleanup

Done when:

1. 24-hour soak on two radios has no corruption and acceptable lag.
2. Alerts are actionable with documented recovery steps.

## Test Plan (Required)

Unit tests:

1. Canonical key determinism across decode/no-decode packet shapes.
2. Observation merge semantics for repeated sightings.
3. Outbox scheduler backoff behavior.

Integration tests:

1. Two radios, same packet: `1 canonical + 2 observations`.
2. Replayed sync batch: idempotent no-op.
3. Upstream down: queue grows under cap, local ingest unaffected.
4. Upstream up: backlog drains without canonical duplication.

Fault tests:

1. Receiver crash before commit vs after commit.
2. Sender restart mid-batch.
3. SQLite write contention under ingest + sync concurrency.

## Immediate Branch Tasks (Next 1-2 Sessions)

1. Add `event_key` module and tests first.
2. Add new schema objects and migration hooks.
3. Wire multi-source manager in runtime context behind a config flag.
4. Add source status endpoint before UI changes.

## ZIP Workflow Recommendation

Preferred:

1. Keep external ZIP outside repo.
2. Extract under `/tmp`.
3. Review diffs and selectively bring in content.

Not recommended:

1. Committing the ZIP blob into repo.
2. Bulk copying ZIP tree over the branch.
