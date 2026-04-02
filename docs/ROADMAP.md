# Meshyface Roadmap

Doc status: active-planning
Last reviewed: 2026-03-14

Meshyface is the working title for “Meshtastic Deep Dashboard, but chat‑first” — with a bonus goal: **explorable public rooms** that feel like AOL/Prodigy chatrooms, without spamming the standard Meshtastic public text feed.

This roadmap is written to be directly hand‑offable to a coding agent (Codex) and to a human reviewer.

## Status (Audited 2026-03-14)

- Milestone 0 is largely complete.
- Milestones 1-5 remain planned work (Rooms are not implemented yet in this branch).
- This document is planning/backlog guidance; current behavior should always be verified against code.

## Guiding principles

- **Don’t break normal Meshtastic chat.** “Everyone” stays clean and interoperable.
- **Rooms are public by default.** No auth, no “admin rights” consensus system in v1.
- **Keep the runtime boring.** Single process, LAN hosted, SQLite optional.
- **Small steps + tests.** Add tiny pure helpers + pytest before big refactors.

## Current baseline (what already exists)

- `/api/state` provides `traffic.recent_chat` and `traffic.recent_packets` plus nodes/summary.
- Frontend already has a “channel” switcher with two scopes: **Everyone** and **Peer‑to‑peer**.
- Direct messages request ACK and show delivery state.
- History store persists chat and packets as JSON blobs.
- Theme system is centralized with runtime presets + persistence.

## Milestones

### Milestone 0 — Docs + naming + handoff hygiene

**Goal:** make the repo easy to pick up by a new contributor (or agent) and reduce doc drift.

**Deliverables**

- ✅ `docs/REPO_STRUCTURE.md` describes *how the system works*, not an exhaustive file list.
- ✅ `docs/PROJECT_PLAN.md` updated to reflect “Rooms” as a first‑class direction.
- ✅ Root `README.md` deployment instructions match current code layout (`meshdash/` must be copied).
- Add a “working title” note everywhere branding appears (Meshyface vs Meshtastic Deep Dashboard).

**Acceptance criteria**

- Someone can deploy from `README.md` without discovering missing files.
- Docs point to exactly one active roadmap (`docs/ROADMAP.md`).

**Codex‑friendly tasks**

- N/A (mostly docs), but safe for agent.

---

### Milestone 1 — Rooms MVP (UI + parsing only)

**Goal:** prove the UX: rooms appear in a list when traffic is observed, and selecting a room filters the chat feed.

**Important constraint:** this milestone can be done *without* any new packet types. It can run on existing `traffic.recent_chat`.

**Scope**

- Add “Rooms” section to left chat navigator.
- Discover rooms by parsing message text using a lightweight convention (interoperability mode), for example:
  - `#retro hello` → room `retro` message `hello`
  - `#help wifi antenna?` → room `help`
- Room list shows:
  - room name
  - last seen timestamp
  - last message preview
  - unread count (same as existing channel unread system)
- Selecting a room filters chat feed to only those messages.

**Implementation notes (hotspots)**

- Frontend:
  - `meshdash/assets/dashboard.js.chat.state.messaging.send_flow.tmpl` (`classifyMessageChannel(msg)`)
  - `meshdash/assets/dashboard.js.chat.render.tmpl` (dynamic channel list rendering)
  - `meshdash/assets/dashboard.js.chat.state.core.tmpl` (`applyChatChannel(...)` + persistence)
  - Extend `classifyMessageChannel(msg)` to return `room:<slug>` when prefix matches.
  - Extend the channel list builder to include discovered rooms.
  - Extend `applyChatChannel(...)` and localStorage persistence to accept dynamic keys.
- No backend changes required.

**Acceptance criteria**

- Rooms appear/disappear based on traffic.
- “Everyone” and “Peer‑to‑peer” still work exactly as before.
- Malformed room tags do not crash rendering.

**Risks / mitigations**

- Room tags will be visible in normal Meshtastic apps (because they’re plain text).
  - That’s acceptable for MVP, but the next milestone removes this disruption.

---

### Milestone 2 — Sideband rooms (don’t pollute public chat)

**Goal:** send and receive room traffic on a dedicated Meshtastic portnum so the standard public text feed stays clean.

This is the key milestone for your stated requirement: **all public, but not disruptive**.

**Scope**

- Define a Meshyface application port (suggested default: `257` in the private range 256–511).
- Implement sending room messages as low‑level MeshPackets (`_sendPacket`) with:
  - `destinationId = "^all"`
  - `channel = 0` (or user‑selected channel index)
  - `decoded.portnum = <meshyface_port>`
  - `decoded.payload = <encoded room payload>`
- Implement receive‑side decode:
  - When packets arrive with the Meshyface portnum, decode payload into a chat entry with `room_id` and `text`.
- Frontend:
  - Rooms are now discovered from `room_id` metadata (not from text tags).
  - Add a room composer mode: selecting a room sets the send target to that room.

**Implementation notes (hotspots)**

- Send path:
  - `meshdash/services_chat.py` (extend to support room sends)
  - `meshdash/mesh_ops.py` (add `send_room_packet(...)` similar to `send_emoji_reaction_packet`)
  - `meshdash/api_chat.py` + `meshdash/api_input_chat.py` (extend API request contract)
- Receive path:
  - `meshdash/tracker_entries.py` (wrap `build_chat_entry_from_packet` to decode room payload)
  - Inject wrapper via `meshdash/tracker_runtime_receive.py` (preferred) to minimize blast radius.
- Persistence:
  - `history_store.save_chat(...)` already stores JSON blobs → no schema migration needed.

**Acceptance criteria**

- Room traffic does **not** show up as normal text messages in “Everyone”.
- Rooms still appear and are selectable.
- Existing chat send (Everyone/direct) unchanged.
- Tests exist for:
  - payload encode/decode
  - chat entry decode from a mocked packet

---

### Milestone 3 — Room discovery + directory packets

**Goal:** rooms become self‑describing and explorable, not just “a list of slugs”.

**Scope**

- Define packet types:
  - `ROOM_ADVERT`: `room_id`, `title`, optional `topic`, optional `ttl`
  - `ROOM_MSG`: `room_id`, `text`
- UI:
  - Room list shows title/topic if known.
  - “Lobby” view lists recent room adverts with previews.
  - A room can be “pinned” so it doesn’t disappear when TTL expires.
- Discovery rules (anti‑spam):
  - Ignore rooms with invalid IDs.
  - Soft‑limit how many new rooms can be added per time window.
  - Optional: only show rooms that have been observed from ≥2 unique senders.

**Implementation notes**

- Back end can attach `room_title`, `room_topic` fields to chat entries when advert info is known.
- Front end keeps a local room registry (in memory + localStorage), keyed by `room_id`.

**Acceptance criteria**

- Rooms become explorable *without* joining.
- Spammy room IDs do not DOS the UI.

---

### Milestone 4 — Backscroll + history UX

**Goal:** rooms feel like “real rooms” with history beyond the last N packets.

**Scope**

- Add a history endpoint for chat/rooms (server‑side filter + pagination), e.g.:
  - `GET /api/history/chat?room_id=retro&limit=200&before=<unix>`
- UI implements “Load older messages” when viewing a room.
- Store retention policies remain global (existing history policy machinery).

**Acceptance criteria**

- Rooms can be browsed backwards without increasing the global packet buffer.
- The endpoint is safe under load (limits, validation).

---

### Milestone 5 — Polishing + extensibility

**Goal:** make it feel like a product and keep future features cheap.

**Candidates**

- Mute/ignore rooms.
- Per‑room notification settings.
- “Who’s here” heuristics (approximate presence from recent messages).
- Optional bridges:
  - IRC bridge (LAN‑local gateway) **as a separate process**.
  - Webhooks for logging.

**Acceptance criteria**

- Adding a new “app message type” doesn’t require touching 10 unrelated files.

## Suggested work split (Codex vs human)

Codex is great at:

- mechanical refactors
- adding small helper modules
- wiring new endpoints + request validation
- writing pytest coverage

Humans should own:

- protocol decisions (payload format, anti‑spam rules)
- UX decisions (what the room list shows, how discovery behaves)
- release decisions (interop mode defaults, backcompat)

## Open decisions (capture before Milestone 2)

- Final portnum value for Meshyface app packets (recommend making it configurable).
- Payload format (text vs binary TLV) — see `docs/ROOMS_SPEC.md`.
- Default discovery TTL and anti‑spam heuristics.
