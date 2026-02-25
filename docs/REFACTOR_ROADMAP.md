# Mesh Dashboard Refactor Roadmap

## Goals

- Make UI/theme changes predictable and low-risk.
- Reduce the `mesh_dashboard.py` blast radius.
- Move toward modular features with focused tests.
- Keep deployment simple (`mesh_dashboard.py` remains the runtime entrypoint).

## Guiding Rules

- No large rewrites in one pass.
- Each phase must keep the app deployable.
- Each extraction must add or preserve tests.
- Prefer pure modules first, then stateful/runtime splits.

## Phase 1: Theme Source Of Truth (started)

### Delivered

- Added `meshdash/theme.py` with centralized theme tokens:
  - `LIGHT_THEME_VARS`
  - `DARK_THEME_VARS`
  - `build_theme_css()`
- `mesh_dashboard.py` now injects theme CSS from this module.
- Added `tests/test_theme.py`.

### Next in phase

- Move repeated color literals to CSS vars where practical.
- Add optional theme preset loader (future user-selectable color packs).

## Phase 2: HTML/CSS/JS Template Boundaries

### Target

Split `_render_html()` into composable builders while keeping server behavior unchanged.

### Delivered

- Added HTML composable pipeline:
  - `meshdash/html_context.py`
  - `meshdash/html_css.py`
  - `meshdash/html_js.py`
  - `meshdash/html_sections.py`
  - `meshdash/html_template.py` (orchestrator)
- Extracted large template bodies into asset templates:
  - `meshdash/assets/dashboard.css.tmpl`
  - `meshdash/assets/dashboard.js.tmpl`
  - `meshdash/assets/dashboard.html.tmpl`
- Added cached asset loader:
  - `meshdash/html_assets.py`
- Added/updated HTML renderer coverage:
  - `tests/test_html.py`
  - `tests/test_html_assets.py`
  - `tests/test_html_sections.py`

### Steps

1. Keep Python-side builders thin and move future UI edits to `meshdash/assets/*`.
2. Add optional lint/minify checks for template assets in CI.
3. Track frontend behavior slices (chat/network/saved) with focused render assertions.

### Exit criteria

- `mesh_dashboard.py` loses most static UI text volume.
- No UI behavior regressions in chat/network/saved views.

## Phase 3: Data/State Service Layer

### Target

Separate state assembly from HTTP wiring.

### Delivered

- Added `meshdash/state_service.py` with dedicated `/api/state` assembly orchestration:
  - tracker snapshot data fanout
  - node saved-count/capability merge
  - local-state safe load + modem preset extraction
  - summary payload composition
  - secret redaction gate
- `meshdash/state.py` is now a thin compatibility facade over the service.
- Added `tests/test_state_service.py`.

### Steps

1. Expand service coverage for failure/partial-data cases (missing metadata, tracker exceptions).
2. Keep request handlers thin:
   - parse request
   - call service
   - encode response

### Exit criteria

- Core view-data logic is importable without HTTP server boot.
- Added unit tests for state assembly edge cases.

## Phase 4: HistoryStore Split

### Target

Break `HistoryStore` into smaller repositories.

### Delivered

- Introduced runtime-focused `HistoryStore` split helpers:
  - `meshdash/history_store_runtime_init.py`
  - `meshdash/history_store_runtime_maintenance.py`
- `meshdash/history_store_runtime_impl.py` now delegates constructor field/connection setup and close/prune lifecycle to those helpers.
- Split history IO wrappers into domain modules while keeping facade compatibility:
  - `meshdash/history_store_packets.py`
  - `meshdash/history_store_chat.py`
  - `meshdash/history_store_connections.py`
  - `meshdash/history_store_nodes.py`
- Added centralized history retention/limit policy helper:
  - `meshdash/history_store_policy.py`
- Added policy-aware history connection/prune entrypoints in `meshdash/history_store_connection.py` and wired runtime init/maintenance to policy-first flow.
- Added targeted tests:
  - `tests/test_history_store_runtime_init.py`
  - `tests/test_history_store_runtime_maintenance.py`
  - `tests/test_history_store_io_wrappers.py` domain-wrapper coverage
  - `tests/test_history_store_policy.py`
  - tighter node-history and online-activity wrapper delegation assertions in `tests/test_history_store_io_wrappers.py`

### Steps

1. `meshdash/history/db.py` (connection + schema) optional namespace consolidation.
2. Decide whether to deprecate/keep `history_store_reads.py` and `history_store_writes.py` compatibility facades.
3. Add tighter tests around node-history and online-activity domain wrappers.

### Exit criteria

- Lower cognitive load for history changes.
- Focused tests per repository module.

## Phase 5: API Endpoint Modules

### Target

Route handlers by domain.

### Delivered

- Added initial domain API modules used by GET route dispatch:
  - `meshdash/api_system.py` for `/api/state`
  - `meshdash/api_history.py` for `/api/history/node` and `/api/history/online`
- Split history API domain helpers into focused modules:
  - `meshdash/api_history_node.py`
  - `meshdash/api_history_online.py`
  - `meshdash/api_history.py` now acts as compatibility facade.
- Added `meshdash/api_chat.py` for `/api/chat/send` POST domain handling.
- `meshdash/http_routes_get.py` now delegates domain payload/response logic into those modules.
- `meshdash/http_routes_post.py` now delegates chat-send behavior into `api_chat`.
- Split HTTP API wiring into focused dispatch modules:
  - `meshdash/http_api_get.py`
  - `meshdash/http_api_post.py`
  - `meshdash/http_api.py` now serves as the orchestration facade.
- Added typed HTTP route dependency contracts:
  - `meshdash/http_route_contracts.py`
  - `DashboardGetRouteDependencies`
  - `DashboardPostRouteDependencies`
- `meshdash/http_api.py` now builds immutable route dependency objects and passes them into route handlers.
- `meshdash/http_routes_get.py` and `meshdash/http_routes_post.py` now consume typed dependency bundles instead of long keyword argument lists.
- Split API input parsing by domain:
  - `meshdash/api_input_chat.py`
  - `meshdash/api_input_history.py`
  - `meshdash/api_inputs.py` now acts as compatibility facade.
- Added focused tests:
  - `tests/test_api_system.py`
  - `tests/test_api_history.py`
  - `tests/test_api_chat.py`

### Steps

1. `meshdash/api/chat.py`
2. `meshdash/api/network.py`
3. `meshdash/api/history.py`
4. `meshdash/api/system.py`

### Exit criteria

- Endpoint behavior grouped by domain.
- Easier feature ownership and review.

## Phase 6: User-Selectable Theme Presets

### Target

Allow operator theme presets without editing code.

### Delivered

- Added `meshdash/theme_presets.py`:
  - default preset builder from current light/dark token maps
  - JSON preset loader with schema validation and safe fallback
  - preset selector with default fallback
- Extended `build_theme_css()` in `meshdash/theme.py` to accept optional token-map overrides.
- Added runtime integration for preset selection:
  - new CLI/env theme args (`--theme-presets`, `--theme-preset`)
  - selected preset tokens now flow into HTML theme CSS rendering
- Added `tests/test_theme_presets.py`.

### Steps

1. JSON theme schema (light/dark token maps).
2. Safe validation + fallback to defaults.
3. Settings endpoint + local persistence.

### Exit criteria

- Users can switch palette presets at runtime.
- Default theme remains the stable baseline.

## Phase 7: Typed Runtime Wiring Contracts

### Target

Reduce string-key coupling between runtime builders and orchestration modules.

### Delivered

- Added `DashboardRuntimeContext` dataclass in `meshdash/dashboard_runtime_context.py` and moved runtime consumer access to typed attributes.
- Added `DashboardServerParts` dataclass in `meshdash/dashboard_server.py` and moved runner access to typed attributes.
- Added `DashboardRuntimeLoaders` dataclass in `meshdash/dashboard_runtime_loaders.py` and moved runtime context assembly off string-key loader dicts.
- Added `TrackerDeliveryCallbacks` dataclass in `meshdash/tracker_callbacks.py` and moved tracker runtime init wiring off callback dict keys.
- Added `TrackerHistoryBootstrap` dataclass in `meshdash/tracker_bootstrap.py` and moved tracker setup bootstrap handoff off dict keys.
- Added `RevisionInfo` dataclass in `meshdash/revision.py` and wired startup/server metadata to typed revision contracts while preserving API payload dict shape.
- Added `DashboardRuntimeDependencies` dataclass in `meshdash/wiring_runtime.py` and moved startup dependency assembly off ad-hoc dict payloads.
- `mesh_dashboard.py` now passes runtime dependency attributes explicitly into `run_dashboard_runtime()` (no kwargs dict shim).
- Added `meshdash/runtime_types.py` shared callback/type aliases and applied them across runner/context/wiring contracts.
- Extended `meshdash/runtime_types.py` with tracker receive/record callback aliases and applied them in tracker packet/runtime dependency modules.
- Added `TrackerReceiveRuntimeState` protocol in `meshdash/tracker_runtime_types.py` and applied it to receive-path dependency assembly/wiring entrypoints.
- `runtime_state_loader` now accepts `RevisionInfo` and performs dict conversion at the state-payload boundary.
- Reused shared HTTP route type aliases across API domain modules (`api_system`, `api_chat`, `api_history_node`, `api_history_online`) to reduce duplicated callable signatures.
- Added typed tracker packet-ingest dependency contract:
  - `TrackerPacketRuntimeDependencies` in `meshdash/tracker_runtime_packet_contracts.py`
  - `record_tracker_packet_unlocked_with_dependencies(...)` in `meshdash/tracker_runtime_record.py`
  - `tracker_runtime_receive` now routes through the typed path by default while preserving legacy callback override compatibility.
  - `tracker_runtime_receive_dependencies.py` now centralizes dependency assembly and legacy kwargs mapping for receive-path compatibility.
  - existing `record_tracker_packet_unlocked(...)` preserved as compatibility wrapper.
- Added typed chat-send parse contract:
  - `ChatSendRequest` dataclass in `meshdash/api_inputs.py`
  - `parse_chat_send_request(...)` now used by POST route wiring + chat API handler
- Added typed node-history query parse contract:
  - `NodeHistoryQuery` dataclass in `meshdash/api_inputs.py`
  - `parse_node_history_request(...)` now used by GET route wiring + history API handler
- Added typed online-activity query parse contract:
  - `OnlineActivityQuery` dataclass in `meshdash/api_inputs.py`
  - `parse_online_activity_request(...)` now used by GET route wiring + history API handler
- Kept `parse_chat_send_body(...)` as a compatibility helper for dict-shaped callers.
- Kept `parse_node_history_query(...)` as a compatibility helper for tuple-shaped callers.
- Kept `parse_online_activity_query(...)` as a compatibility helper for scalar callers.

### Steps

1. Consider stricter type aliases/protocols for callback signatures used in runtime wiring.
2. Triage remaining dict-shaped payloads where they represent transport formats vs internal contracts.

### Exit criteria

- Runtime orchestration uses typed object contracts for core boot/server handoff.
- Fewer string-key regressions during future refactors.
