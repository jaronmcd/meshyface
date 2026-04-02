# Multi-Radio Federated Backend Plan (V2, Greenfield)

Doc status: proposal
Last reviewed: 2026-03-14

Status (audited 2026-03-14):

1. Proposal/spec document only.
2. The V2 multi-radio ingest/sync model described here is not implemented in this branch.

## Decision

Build a new V2 backend architecture that is allowed to break old assumptions.

1. No backward-compatibility requirement.
2. No legacy patch constraints.
3. Prioritize correctness, dedupe integrity, and sync reliability.

## What We Are Building

A backend can run in dual role:

1. Local collector:
   - ingest one or more radios
   - write to local DB
2. Uplink contributor:
   - forward canonical events to another backend
   - retry until acknowledged

And optionally:

1. Aggregator backend:
   - accept events from many collectors
   - dedupe and aggregate globally
   - serve frontend queries

Frontend deployment options:

1. Casual mode: connect to a local collector backend.
2. Aggregated mode: connect to a central aggregator backend.

Primary platform outcome:

1. Any radio on the network can contribute observations/events into the shared database path (directly or via collector-to-aggregator sync).

## Core Requirements

1. Duplicate receptions from different radios must not inflate canonical counts.
2. Per-radio and per-backend observations must be preserved for RF insight.
3. Backend-to-backend sync must be idempotent.
4. Sync loops must be prevented by design.
5. Local ingest must continue when upstream is offline.

## Consistency Model

Eventual consistency with idempotent replay.

1. Local ingest commits first.
2. Upstream sync is asynchronous.
3. Duplicate deliveries are safe.
4. Ordering is best-effort, not globally strict.

## Event Identity and Dedupe

Define one canonical event key used everywhere.

**V2.1 frozen spec:** `docs/MULTI_RADIO_V2_1_FROZEN_SPEC.md`

## Canonical Key (`event_key`) (V2.1)

Canonical identity is defined by the frozen spec:

* primary: `from_num_u32 + packet_id_u32` (sender-assigned, wire-stable)
* fallback: `from_num_u32 + wire_payload_bytes` hash (only if `packet_id` missing)
* **no decode-only fields** (e.g. `portnum`) and **no observer-local fields** (e.g. RSSI/SNR/hops/time buckets)

Rules (V2.1):

1. Canonical insert is unique on `event_key`.
2. Observations are **aggregated** and upserted uniquely on `(event_key, backend_id, source_id)`.
3. Canonical dedupe horizon is bounded by canonical retention policy (see frozen spec §4).

## Data Model (V2)

Use additive, purpose-built tables for canonical-vs-observation separation.

## Tables

### `backends`

1. `backend_id` primary key
2. `role` (`collector`, `aggregator`, `hybrid`)
3. `created_unix`
4. `last_seen_unix`

### `sources`

1. composite primary key `(backend_id, source_id)`
2. `backend_id` foreign key
3. `source_mode` (`serial`, `tcp`, `remote`)
4. `endpoint`
5. `enabled`
6. `last_seen_unix`

### `events_canonical`

1. `event_key` primary key
2. `origin_backend_id`
3. canonical packet fields (from/to/port/channel/payload/meta)
4. `first_seen_unix`
5. `first_source_id`

### `event_observations`

1. aggregated observation row keyed by `(event_key, backend_id, source_id)`
2. fields include:
   - `first_seen_unix`, `last_seen_unix`, `seen_count`
   - min/max RSSI/SNR (optional)
   - min/max hops (optional)

### `sync_peers`

1. `peer_backend_id` primary key
2. endpoint/auth metadata
3. enabled flag
4. last success/failure timestamps

### `sync_outbox`

1. `id` primary key
2. `peer_backend_id`
3. `item_type` (V2.1 MVP uses `event` only)
4. `item_key` (V2.1: `event_key`)
5. `item_hash` (hash of canonical sync payload)
6. serialized envelope
7. `attempt_count`
8. `next_attempt_unix`
9. `last_error`
10. `acked_unix`
11. unique index on `(peer_backend_id, item_type, item_key)` for **coalescing**

### `sync_inbox_seen`

1. `sender_backend_id`
2. `item_type`
3. `item_key`
4. `item_hash`
5. `seen_unix`
6. primary key `(sender_backend_id, item_type, item_key, item_hash)`

Purpose:

1. guarantees idempotent accept on remote ingest endpoint.

## Ingest Pipeline (Collector)

For each received packet:

1. Normalize packet fields.
2. Compute `event_key`.
3. Upsert canonical event:
   - insert if missing
   - merge/enrich if exists (fill-NULL-only; see frozen spec)
4. Upsert aggregated observation row for this source.
5. Enqueue outbox record(s) for configured peers **only when sync-worthy canonical fields change**.

Critical property:

1. Canonical metrics depend on canonical rows, not raw observations.

## Sync Protocol (Backend to Backend)

## Endpoint

1. `POST /sync/v1/events/batch`

Request:

1. list of envelopes with:
   - `item_type` (V2.1 MVP uses `event` only)
   - `item_key` (V2.1: `event_key`)
   - `item_hash` (hash of canonical sync payload)
   - `origin_backend_id`
   - `sender_backend_id`
   - canonical payload
   - `sent_unix`

Response:

1. per-item status:
   - `acked`
   - `duplicate`
   - `conflict`
   - `rejected`
   - `retry`
2. optional retry hints

## Idempotency Rules

1. Receiver checks `(sender_backend_id, item_type, item_key, item_hash)` in `sync_inbox_seen`.
2. If seen, return `duplicate` and no mutation.
3. If unseen, record inbox marker and apply canonical upsert.

## Loop Prevention

1. Envelope includes `origin_backend_id`.
2. In MVP, aggregators are terminal and do not forward any items.
3. Sender outbox coalesces on `(peer_backend_id, item_type, item_key)`.

## Sync Worker

1. Pull due outbox rows by `next_attempt_unix`.
2. Send batches with size caps.
3. Mark ACKed rows complete.
4. Retry failures with exponential backoff and jitter.
5. Emit queue depth and error metrics.

## Security

V2 minimum:

1. static token auth per peer
2. TLS required for remote transport

Recommended next:

1. mTLS between backends
2. per-peer key rotation
3. signed envelope payload hash

## Observability and Ops

Expose:

1. `GET /api/sync/status`
2. `GET /api/sources/status`
3. queue depth, retry rate, last ACK time, per-peer error counters
4. dedupe hit ratio (canonical skipped vs inserted)

Alerting:

1. outbox age high watermark
2. sustained peer failures
3. abnormal dedupe collision/fallback-key rates

## Implementation Plan

## Phase 1: V2 Local Canonical Core

1. Implement canonical key generation.
2. Create V2 schema tables (`events_canonical`, `event_observations`, `sources`).
3. Route ingest through canonical-first pipeline.

Done when:

1. two local radios hearing same packet produce one canonical row and multiple observations.

## Phase 2: Multi-Source Runtime

1. Add multi-interface source manager.
2. Attach stable `source_id` to receive path.
3. Track per-source health.

Done when:

1. mixed serial/tcp local source ingest is stable under load.

## Phase 3: Outbox Uplink

1. Add `sync_peers`, `sync_outbox`.
2. Add retry worker with backoff+jitter.
3. Add sync status endpoints.

Done when:

1. upstream outages do not impact local ingest and backlog drains on recovery.

## Phase 4: Remote Ingest Endpoint

1. Implement `/sync/v1/events/batch`.
2. Add inbox idempotency table.
3. Enforce loop rules.

Done when:

1. replaying same batch is no-op and returns duplicate ACKs.

## Phase 5: Frontend Mode Clarity

1. Add explicit backend mode metadata in API.
2. Frontend surfaces mode:
   - local collector
   - aggregator
   - hybrid

Done when:

1. operators can clearly see where data is sourced and whether sync is healthy.

## Test Plan

## Unit Tests

1. canonical key generation and fallback behavior
2. dedupe window semantics
3. outbox retry scheduling logic
4. loop-prevention rule checks

## Integration Tests

1. two radios same packet -> one canonical, two observations
2. collector to aggregator sync -> idempotent insert on repeated deliveries
3. upstream down -> outbox grows, local queries still correct
4. recovery -> backlog drains without duplicates

## Fault Injection

1. delayed ACKs
2. partial batch failures
3. clock skew across nodes
4. repeated replay attempts

## Deployment Strategy

No compatibility bridge required. Treat as V2 cutover.

1. deploy V2 backend schema and runtime as a new release line
2. validate in staging with synthetic multi-radio traffic
3. promote collector first, then aggregator
4. monitor queue depth/dedupe metrics before full rollout

Rollback:

1. stop sync workers
2. run collector-only mode
3. preserve V2 data for postmortem and retry later

## Open Decisions

1. Envelope size limits and compression defaults.
2. Minimum security baseline accepted for first production rollout.
3. Post-MVP: whether to add typed observation sync.
