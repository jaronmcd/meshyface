# Multi-Radio V2.1 Frozen Spec (Normative)

Doc status: proposal-normative
Last reviewed: 2026-03-14

Status: **FROZEN (V2.1)**

Implementation note (audited 2026-03-14): this is a normative design spec for a planned V2 system; it is not yet implemented in this branch.

This spec is the source of truth for V2.1 implementation. If another doc disagrees,
this doc wins.

## 1) Roles and topology (MVP)

* **Collector**: ingests ≥1 radios (“sources”) into local SQLite; may sync upstream.
* **Aggregator**: receives fan-in sync; serves reads.

**MVP topology is strictly one-way:** **collector → aggregator only**.

* Collectors MUST NOT sync to other collectors.
* Aggregators MUST NOT forward (aggregator is terminal in MVP).

## 2) Sync scope (MVP)

**Events-only sync in MVP.**

* Canonical events MAY sync upstream.
* Observations MUST remain local-only in MVP.

## 3) Event identity (`event_key`) (no decode-only or observer-local fields)

### Primary identity

`event_key` MUST be derived only from stable sender-assigned fields:

* `from_num_u32` (packet["from"] if parseable uint32; else parse packet["fromId"] if it is `!` + 8 hex)
* `packet_id_u32` (packet["id"] if parseable uint32 and > 0)

Primary serialization (exact):

```
event_key = f"e21:{from_num_u32:08x}:{packet_id_u32:08x}"
```

### Fallback identity (only if packet_id missing/<=0)

Fallback is permitted only if the ingest layer provides the encrypted wire payload bytes.

* required: `wire_payload_bytes` (encrypted payload bytes as received on-air)
* required: `from_num_u32`

Fallback serialization (exact):

```
payload_sig_hex = blake2s(wire_payload_bytes, digest_size=16).hexdigest()
event_key = f"f21:{from_num_u32:08x}:{payload_sig_hex}"
```

If `packet_id_u32` is missing/<=0 AND `wire_payload_bytes` is not available, the
packet is **UNKEYABLE** (see §7).

## 4) Canonical dedupe horizon (packet-id reuse rule)

To avoid “forever-dedupe” dropping valid future packets if packet IDs are reused,
V2.1 requires a **finite canonical retention horizon**:

* `events_canonical` MUST be pruned by time (event retention seconds) and/or row
  cap.
* Default MUST be finite (operators may configure it larger, but not “infinite”).

Operational meaning:

* Dedupe is guaranteed only within the retained window.
* If a sender reuses a packet ID after the original event has been pruned, it will
  be accepted as a new event.

## 5) Canonical enrichment (merge precedence)

For identical `event_key`, merges MUST be monotonic and order-independent:

1. Identity invariants (`from_num_u32`, `packet_id_u32` if stored) never change.
2. `first_seen_unix = min(existing, incoming)`
3. `last_seen_unix  = max(existing, incoming)`
4. Decoded/enriched fields are “fill-NULL-only” (never overwrite non-empty with
   empty/NULL).
5. `raw_packet_json` is replaced only if incoming is strictly “more informative”
   by `info_score = count_non_empty([decoded.portnum, decoded.text, decoded.position,
   decoded.telemetry, decoded.nodeInfo])`.
6. Conflicting non-empty decoded fields MUST be logged to `dedupe_collisions`
   (type=`enrichment_conflict`) and the existing value kept.

## 6) Sync idempotency + outbox coalescing

### Item types

MVP sync sends only:

* `item_type = "event"`
* `item_key = event_key`

### Item hash

`item_hash` MUST be a stable hash of the **sync payload**, using canonical JSON:

```
canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
item_hash_hex = blake2s(canonical_json.encode("utf-8"), digest_size=16).hexdigest()
```

**Sync payload MUST exclude volatile fields** (e.g., `last_seen_unix`, counters),
so that normal duplicate receptions do not create new hashes.

### Receiver inbox idempotency key

Receiver MUST dedupe by:

* `PRIMARY KEY (sender_backend_id, item_type, item_key, item_hash)`

Meaning:

* same `(item_key, item_hash)` replay → `duplicate`, no mutation
* same `item_key` with new `item_hash` → apply merge once, then idempotent

### Sender outbox uniqueness key (coalescing)

Sender outbox is **one row per item_key**:

* `UNIQUE (peer_backend_id, item_type, item_key)`

On enqueue of an item with the same uniqueness key:

* If `incoming.item_hash == existing.item_hash`: no-op.
* Else: **replace** `payload_json` and `item_hash`, and clear `acked_unix`.

**Important:** sender MUST only mark a row acked if the ACKed `item_hash` equals
the row’s current `item_hash` (to avoid “stale ACK” races after replacement).

## 7) Unkeyable packets (classification + surfacing)

**UNKEYABLE** means the item cannot produce an `event_key` under §3.

Unkeyable reasons (MUST be counted and exposed):

* `missing_sender`: cannot parse `from_num_u32` from packet["from"] or a strict
  hex packet["fromId"].
* `missing_packet_id`: packet["id"] missing/unparseable/<=0 AND no fallback payload.
* `missing_wire_payload`: packet_id missing/<=0 and `wire_payload_bytes` unavailable.
* `bad_shape`: packet is not a dict or required fields are invalid types.

Surfacing requirements:

* Counter: `ingest_unkeyable_total{backend_id, source_id, reason}`
* API: include per-source unkeyable counts and last reason in `/api/sources/status`
* Logging: rate-limited warning per source (include reason + minimal packet summary)
