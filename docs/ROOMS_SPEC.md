# Rooms spec (public, discoverable, non‑disruptive)

Doc status: active-planning-spec
Last reviewed: 2026-03-14

Status (reviewed 2026-03-14):

1. This is a forward-looking protocol/UX spec.
2. Rooms are not implemented end-to-end in this branch yet.
3. Current runtime chat behavior is documented in `docs/CHANNELS.md`.

This document defines the “Rooms” feature for Meshyface.

The core idea:

- **Rooms are public.** Anyone on the same Meshtastic channel can read/send.
- **Rooms are discoverable.** If you hear room traffic, the room appears in your UI.
- **Rooms are non‑disruptive.** Room traffic should *not* pollute the normal “Everyone” text feed.

## Requirements

These are target requirements for implementation milestones, not statements of already-shipped behavior.

### Hard requirements

- The existing “Everyone” experience must remain clean and interoperable.
- Rooms must appear/disappear based on observed traffic.
- Joining a room is a UI action (there is no membership protocol in v1).

### Soft requirements

- Works over very low bandwidth.
- Robust against malformed payloads.
- Doesn’t allow one spammer to create 10,000 fake rooms and freeze the browser.

## Transport options

### Option A — Prefix tags in normal TEXT_MESSAGE_APP

Example: `#retro hello`.

- ✅ Zero backend changes
- ✅ Works with any client (everyone can read it)
- ❌ Pollutes the public feed with “room syntax”

Use this only for Milestone 1 (MVP) or as an **interop mode**.

### Option B — Meshyface app packets on a private portnum

Use a dedicated app port (256–511). Only Meshyface understands it.

- ✅ Does not pollute “Everyone”
- ✅ Still public (anyone on channel receives packets)
- ✅ Allows adverts + metadata
- ❌ Other clients won’t display it (by design)

This is the recommended default for Meshyface.

### Option C — Separate Meshtastic channels

Technically “real channels”, but limited in count and require shared channel configs/PSKs.

- ✅ Built‑in isolation
- ❌ Not discoverable in the way AOL rooms were
- ❌ Operational friction (sharing configs)

Not recommended for the AOL‑style room list UX.

## Proposed protocol (Option B)

### Portnum

- Use a portnum in Meshtastic’s private application range: **256–511**.
- Suggested default: **257** (configurable).

> Note: using `256 (PRIVATE_APP)` risks collisions with other “random private” apps.
> A fixed, configurable value reduces collisions.

### Packet destination + channel

- `destinationId = "^all"`
- `packet.channel = <channel_index>` (default 0)

Rooms are “within a Meshtastic channel”.

### Payload encoding

You want payloads that are:

- small
- easy to validate
- versioned

#### v1 binary TLV (recommended)

All multi‑byte integers are unsigned big‑endian.

```
Byte 0:  version = 1
Byte 1:  kind
         1 = ROOM_ADVERT
         2 = ROOM_MSG
         3 = ROOM_TOPIC (optional)
Byte 2:  room_id_len (0..32)
Bytes 3..(3+room_id_len-1): room_id (ASCII)
Remaining bytes: UTF-8 body (interpretation depends on kind)
```

Body formats:

- `ROOM_MSG`: body = UTF‑8 text (what appears in the room)
- `ROOM_ADVERT`: body = UTF‑8 title/topic string (short; UI preview)
  - Suggested: `"<title>\n<topic>"` (topic optional)
- `ROOM_TOPIC`: body = UTF‑8 topic string

Validation rules:

- `room_id` must match: `^[a-z0-9][a-z0-9_-]{0,31}$`
- Body max bytes should be bounded (keep under existing chat max bytes)

Why this TLV?

- Easy to implement in Python
- Minimal overhead vs JSON
- Still human‑debuggable (ASCII room id + UTF‑8 body)

#### v1 text framing (fallback)

If decoding bytes from Meshtastic proves annoyingly inconsistent across platforms, a UTF‑8 text framing is acceptable:

```
MF1|<kind>|<room_id>|<body>
```

…but you must then define escaping rules. TLV avoids this.

### Chat entry shape (what the UI should receive)

When a Meshyface packet is decoded, convert it to a standard chat entry dict (similar to `build_chat_entry_from_packet` output) and add room metadata.

Required fields:

- `from`: node id
- `to`: `^all`
- `rx_time` / `captured_at`
- `portnum`: something stable (e.g. `"MESHYFACE_APP"` or the numeric string)
- `text`: decoded room message text (or advert text)
- `room_id`: slug

Optional fields:

- `room_title`
- `room_topic`
- `room_kind`: `"advert" | "msg" | "topic"`

The frontend should classify messages like:

- `channel = "room:<room_id>"` when `room_id` is present
- Otherwise fall back to the existing “Everyone” / “direct” logic

## Discovery + anti‑spam rules

### Discovery

- A room is “discovered” if you see either:
  - `ROOM_ADVERT` for it, or
  - `ROOM_MSG` for it

### Expiration

- Default TTL: expire room from the *active list* after **30 minutes** without traffic.
- Keep a secondary “recently seen” list for another window (optional).
- Allow “pinning” rooms (manual keep‑alive).

### Spam control (minimum viable)

- Hard cap the number of active rooms rendered (e.g., 200).
- Ignore room IDs that fail the regex.
- Rate‑limit adding *new* room IDs per sender per time window.
- Optional: only surface a room in the list after ≥2 messages or ≥2 unique senders.

## Security model (v1)

Rooms are public. Anyone can:

- send to any room id
- spoof titles/topics

Mitigations are UX‑level:

- mute/ignore
- rate limits
- “verified” status only if the user explicitly pins/trusts a room

Do not implement “admins synced at startup” in v1 — it becomes a consensus and identity problem fast.

## Backscroll / history

- MVP uses `traffic.recent_chat` (limited buffer).
- A later milestone adds a history endpoint with pagination.

## Implementation hooks

- Send: add a `send_room_packet(...)` helper modeled after `send_emoji_reaction_packet(...)` in `meshdash/mesh_ops.py`.
- Receive: wrap `build_chat_entry_from_packet(...)` to decode Meshyface payloads.
- UI: extend the existing channel system; rooms become dynamic channels.
