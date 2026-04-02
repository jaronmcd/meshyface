# Repository Structure

Doc status: active-runtime
Last reviewed: 2026-03-14

This repo is deliberately “boring” in the best way:

- One Python process (`mesh_dashboard.py`) runs a tiny HTTP server + Meshtastic connection.
- The frontend is static HTML/CSS/JS templates rendered server‑side, then driven by `/api/*` JSON.
- A tracker keeps recent packets/chat in memory and optionally persists to SQLite.

If you’re coming in to implement **Rooms** (the “90’s chatroom” feature), skip to **Where Rooms plug in**.

## Mental model

### Data flow (end‑to‑end)

1. **Meshtastic interface** delivers packets (serial/TCP) via pubsub callbacks.
2. **Tracker receive path** parses/normalizes each packet and updates:
   - `recent_packets` ring buffer
   - `recent_chat` ring buffer
   - link/port counters
   - optional SQLite history writes
3. **State service** builds the `/api/state` payload from:
   - Meshtastic node DB snapshot (names, positions, lastHeard…)
   - tracker snapshot (recent traffic + counters)
   - history store metadata (retention, counts, rollups)
4. **Browser** polls `/api/state` on a timer and renders:
   - chat feed + roster
   - map
   - nodes table + history panels

### “What do I run?”

- Dev/local: `python mesh_dashboard.py ...`
- Prod: `meshtastic-dashboard.service` runs the same script under systemd.

## Entry points

- `mesh_dashboard.py`
  - CLI + environment defaults
  - runtime wiring
  - theme preset wiring
- `mesh_connection.py`
  - serial/TCP connection abstraction
  - open interface + connection args
- `meshtastic-dashboard.service`
  - systemd unit template

## Backend map (`meshdash/`)

### Runtime/server wiring

These modules exist to keep `mesh_dashboard.py` thin.

- `cli.py` / `cli_args_*.py`: CLI argument definitions and env fallbacks.
- `dashboard_runtime.py` / `dashboard_runner_impl.py`: startup/shutdown orchestration.
- `dashboard_server.py` + `http_api.py` + `http_routes_*.py`: HTTP handler + routes.
- `wiring_runtime.py`: dependency checks + assembly.

### Packet ingest + tracker

This is where “what we heard on the mesh” turns into UI‑friendly state.

- `tracker_runtime_impl.py`: runtime tracker class (buffers + callbacks).
- `tracker_runtime_receive.py`: per‑packet orchestration (parse → observe → store).
- `tracker_ingest.py`: parse a raw packet into a normalized “parsed packet”.
- `tracker_entries.py`: build packet summary rows + chat entry rows.
- `tracker_storage.py`: append to buffers + optional history writes.
- `tracker_snapshot.py`: build snapshot payloads for `/api/state`.

### State assembly

- `state_service.py`: builds the `/api/state` payload.
- `state_summary.py`: summary metrics + metadata.
- `state_payload_contracts.py`: typed payload shims (keeps API dict‑shape stable).

### History store

- `history_store_runtime_impl.py`: SQLite implementation.
- `history_schema_*`, `history_*writes.py`, `history_*read*.py`: schema + write/read helpers.

### Chat send + delivery tracking

- `services_chat.py`: orchestrates send + local echo + response.
- `chat_send_prepare.py`: validates/normalizes send requests.
- `chat_delivery_*`: delivery state tracking for direct messages.
- `mesh_ops.py`: low‑level packet send helpers (used for reactions today; Rooms can reuse this pattern).

### Frontend templates

- `html_template.py` / `html_sections.py` / `html_css.py` / `html_js.py`: render pipeline.
- `assets/dashboard.html.tmpl`, `assets/dashboard.css.*.tmpl`, `assets/dashboard.js.*.tmpl`: UI source of truth (`dashboard.css.tmpl`, `dashboard.js.tmpl`, `dashboard.js.bootstrap.tmpl`, `dashboard.js.chat.tmpl`, `dashboard.js.chat.state.tmpl`, `dashboard.js.chat.state.games.tmpl`, `dashboard.js.chat.state.messaging.tmpl`, `dashboard.js.chat.events.tmpl`, `dashboard.js.chat.events.core.tmpl`, `dashboard.js.chat.events.console.tmpl`, `dashboard.js.chat.events.settings_map.tmpl`, `dashboard.js.chat.events.settings.tmpl`, `dashboard.js.chat.events.data_views.tmpl`, `dashboard.js.runtime.tmpl`, and `dashboard.js.runtime.views.tmpl` are compatibility stubs; runtime CSS is assembled from `dashboard.css.base.tmpl` + `dashboard.css.layout.tmpl` + `dashboard.css.components.tmpl`; runtime JS is assembled from `dashboard.js.bootstrap.map.tmpl` + `dashboard.js.bootstrap.tickers.tmpl` + `dashboard.js.bootstrap.shared.tmpl` + `dashboard.js.ui.shared_controls.tmpl` + `dashboard.js.chat.state.core.tmpl` + `dashboard.js.chat.state.channels.tmpl` + `dashboard.js.chat.state.games.reversi_local.tmpl` + `dashboard.js.chat.state.games.classic.tmpl` + `dashboard.js.chat.state.games.network.tmpl` + `dashboard.js.chat.state.games.ui.tmpl` + `dashboard.js.chat.state.messaging.peers.tmpl` + `dashboard.js.chat.state.messaging.emoji_search.tmpl` + `dashboard.js.chat.state.messaging.send_flow.tmpl` + `dashboard.js.chat.state.messaging.emoji_ui.tmpl` + `dashboard.js.chat.state.files.tmpl` + `dashboard.js.chat.events.core.identity.tmpl` + `dashboard.js.chat.events.core.layout_tables.tmpl` + `dashboard.js.chat.events.core.notifications.tmpl` + `dashboard.js.chat.events.core.navigation.tmpl` + `dashboard.js.chat.events.console.session.tmpl` + `dashboard.js.chat.events.console.commands.tmpl` + `dashboard.js.chat.events.console.formatting.tmpl` + `dashboard.js.chat.events.console.ui.tmpl` + `dashboard.js.chat.events.settings.state_normalize.tmpl` + `dashboard.js.chat.events.settings.channels.tmpl` + `dashboard.js.chat.events.settings.apply_actions.tmpl` + `dashboard.js.chat.events.settings.bindings.tmpl` + `dashboard.js.chat.events.map_selection.tmpl` + `dashboard.js.chat.events.bindings.tmpl` + `dashboard.js.chat.events.data_views.summary_map.tmpl` + `dashboard.js.chat.events.data_views.nodes_saved.tmpl` + `dashboard.js.chat.events.data_views.charts.tmpl` + `dashboard.js.chat.events.data_views.history_fetch.tmpl` + `dashboard.js.chat.render.tmpl` + `dashboard.js.runtime.views.packet_channels.tmpl` + `dashboard.js.runtime.views.encryption.tmpl` + `dashboard.js.runtime.views.raw_data.tmpl` + `dashboard.js.runtime.poll.tmpl` + `dashboard.js.runtime.boot.tmpl`).
- `theme.py`, `theme_presets.py`, `theme_settings.py`: runtime theme switching.

## Where Rooms plug in

Rooms are mostly a **classification + filtering** problem:

- **Receive:** identify that a packet is a “room” packet and turn it into a chat entry with `room_id` metadata.
  - Default chat entries are built in `meshdash/tracker_entries.py` (`build_chat_entry_from_packet`).
  - The per‑packet receive orchestrator lives in `meshdash/tracker_runtime_receive.py` and allows injection of an alternate `build_chat_entry_from_packet_fn`.
- **Persist:** chat history already stores `message_json` blobs; you can add fields like `room_id`, `room_title`, `room_kind` without schema changes.
  - Writes happen via `meshdash/tracker_storage.py` → `history_store.save_chat(...)`.
- **Send:** extend the send service to emit room packets without polluting normal “Everyone” text chat.
  - Current send API is `/api/chat/send` (`meshdash/api_chat.py` + `meshdash/services_chat.py`).
  - Reuse the low‑level `_sendPacket` pattern in `meshdash/mesh_ops.py` (currently used for emoji reactions).
- **UI:** add a Rooms navigator + feed filtering.
- Current channel switcher (“Everyone”, “Peer‑to‑peer”) lives in `assets/dashboard.js.chat.render.tmpl`.
  - Rooms will likely become additional “channels” in the left rail, discovered from traffic.

The concrete plan and protocol are in:

- `docs/ROADMAP.md`
- `docs/ROOMS_SPEC.md`

## How to work in this repo

- Run tests: `pytest -q`
- Prefer adding small pure helpers + tests over “one big refactor PR”.
- Keep HTTP boundaries thin: parse → domain service → response encode.
- Keep backward compatibility at API payload boundaries (dict‑shape stability matters for the frontend).
