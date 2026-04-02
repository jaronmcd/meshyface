# Meshyface Product Plan (working title)

Doc status: active-planning
Last reviewed: 2026-03-14

Status (reviewed 2026-03-14):

1. This is a direction/intent doc, not an implementation checklist.
2. Current runtime truth lives in code plus `docs/CHANNELS.md` and `docs/REPO_STRUCTURE.md`.
3. Rooms remain planned work in this branch.

## North Star

Build a **Teams‑like chat experience for Meshtastic networks** with a splash of **90’s chatroom culture**:

- Chat is primary.
- Network/map/history cards are contextual.
- Operators can move from conversation → node diagnostics → link quality without changing tools.
- Public, explorable **Rooms** appear when you pick up traffic (AOL/Prodigy style).

## Product Direction

1. Chat-first UX
2. Public Rooms (discoverable from traffic; joinable by name)
3. Live + historical telemetry side-by-side
4. Persistent state for replay and benchmarking
5. LAN-hosted, low-friction deployment

## Current Reality Snapshot (This Branch)

- Chat, direct messages, ACK flow, delivery state, and reactions are implemented.
- Chat supports scope switching (`Everyone` / `Peer-to-peer`) and independent View Ch/Send Ch handling.
- Frontend templating is already modularized (`dashboard.js.*.tmpl`, `dashboard.css.*.tmpl`).
- Rooms protocol/discovery behavior is not implemented end-to-end yet.

## Milestones

### Phase 1: Stability Foundation (current)

- Reliable dashboard service + history DB
- Per-message emoji reactions with protocol compatibility
- Node selection syncing across chat/map/list
- Initial tests for core parsing and transport helpers

### Phase 2: Unified Workspace

- Promote chat pane to primary surface
- Context panel updates from selected message/node
- Reduce duplicated cards and merge related panels
- Add better layout presets for desktop vs mobile

### Phase 3: Mesh Intelligence

- Historical trends by node/link (SNR, RSSI, hops)
- Connection reliability scoring over time
- Saved views for antenna/site benchmarking
- Exportable snapshots for analysis

## Non-Goals (for now)

- Full enterprise identity/auth stack
- Cloud multi-tenant backend
- Replacing the official Meshtastic app

## Engineering Plan

1. Keep runtime simple (`mesh_dashboard.py` entrypoint remains)
2. Improve testability with pure helper functions + pytest
3. Incrementally split large modules only after test coverage is in place
4. Keep all deprecated tools in `archive/` with clear labels
5. Treat `docs/REFACTOR_ROADMAP.md` as historical implementation log, not pending mandatory work.

## Definition of Done For New Features

- Works live with existing service deployment flow
- Persists correctly in history (if feature touches chat/traffic)
- Has pytest coverage for parsing/state behavior
- README/docs updated when behavior changes

## Where the “Rooms” plan lives

- Product + engineering milestones: `docs/ROADMAP.md`
- Protocol + UX rules: `docs/ROOMS_SPEC.md`
