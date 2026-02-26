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
  - focused chat/network/saved structure assertions in `tests/test_html.py` to guard key DOM anchors used by frontend behavior.

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
- Added `meshdash/state_tracker.py` with safe tracker read helpers:
  - snapshot fallback to empty typed tracker snapshot on exception
  - saved-count/capability fallback to empty mappings on exception
  - explicit tracker error fields in state payload for degraded paths (`tracker_error`, `tracker_saved_counts_error`, `tracker_capabilities_error`)
- State service now handles node collection failures with empty-node fallback + explicit `nodes_error` payload field.
- State service now safely JSON-normalizes `my_info` / `metadata` with explicit degraded-path fields (`my_info_error`, `metadata_error`) instead of raising.
- Added typed state payload contracts in `meshdash/state_payload_contracts.py`:
  - `StateTrafficPayload` and `DashboardStatePayload` with dict conversion at API boundary
  - compatibility coercion helpers for mapping-shaped callers.
- Replaced loose callable aliases in `meshdash/state_service_contracts.py` with explicit collaborator protocol signatures (node collectors, summary builder, redaction, and safe tracker loaders).
- Split state-service entrypoints:
  - `build_dashboard_state_typed(...)` composes typed payload contracts
  - `build_dashboard_state(...)` remains compatibility wrapper for redaction + dict return shape.
- Aligned state runtime dependency contracts to state service boundaries:
  - `StateSnapshotRuntimeDependencies.tracker` now uses `StateTracker` protocol
  - `storage_probe_path` now typed as `Optional[str]` through runtime state loader/dependency assembly.
- State service now guards summary assembly failures:
  - emits `summary_error` and falls back to a minimal summary payload instead of raising.
- `/api/state` now normalizes both typed and dict state payload returns through `coerce_dashboard_state_payload(...)` at the API boundary before JSON writing.
- Centralized state API-boundary normalization in `normalize_state_payload_for_api(...)` within `meshdash/state_payload_contracts.py`, keeping handler modules transport-thin.
- Tightened state payload/service contracts from broad `Any` to concrete `object` + typed dict shapes across:
  - `state_node_contracts.py`
  - `state_payload_contracts.py`
  - `state_service_contracts.py`
  - `state_summary.py`
  - `state_service.py`
- Replaced loose callable aliases in `meshdash/http_route_contracts.py` with explicit parser/writer protocol signatures for GET/POST dependency wiring.
- Normalized API input parser integer-coercion typing (`api_input_chat.py`, `api_input_history.py`) to shared `runtime_types.ToIntFn` alias.
- Updated `http_api.make_http_handler(...)` to consume shared route-contract types (`StateFn`, `NodeHistoryFn`, `OnlineActivityFn`, `SendChatFn`, `ToIntFn`) instead of local raw callable signatures.
- `meshdash/state.py` is now a thin compatibility facade over the service.
- Added `tests/test_state_service.py` and `tests/test_state_tracker.py`.

### Steps

1. Expand service coverage for failure/partial-data cases (remaining: metadata/service-edge variants).
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
  - shared callback protocol/type aliases for history read modules in `meshdash/history_read_contracts.py` and usage in `history_read_api.py` / `history_read_history.py`
  - explicit callback protocol contracts in `meshdash/history_store_runtime_init.py` for policy builder and history connection openers
  - shared SQL execution protocols in `meshdash/sql_contracts.py` and adoption across history read/write modules to reduce duplicate SQL typing contracts.
  - centralized history runtime store/lock/prune protocol contracts in `meshdash/history_store_runtime_contracts.py` with `history_store_runtime_init.py` and `history_store_runtime_maintenance.py` now consuming the shared contracts.

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
- Applied shared tracker callback aliases across `tracker_ingest.py` and `tracker_receive.py` so parse/process layers share the same contract vocabulary as runtime receive/record wiring.
- Applied shared tracker callback aliases in `tracker_runtime_receive_bindings.py` for resolver and dispatch hook signatures.
- Added `TrackerReceiveRuntimeState` protocol in `meshdash/tracker_runtime_types.py` and applied it to receive-path dependency assembly/wiring entrypoints.
- Added explicit runtime/setup protocol contracts:
  - `meshdash/dashboard_args_contracts.py` (shared runtime/server arg shape)
  - `meshdash/dashboard_setup_contracts.py` (history-store/tracker factory + runtime setup collaborators)
  - `meshdash/runtime_lifecycle_contracts.py` (serve/close lifecycle boundaries)
- Applied those contracts through dashboard runtime setup/orchestration modules:
  - `dashboard_setup.py`
  - `dashboard_runtime_context.py`
  - `dashboard_runner_impl.py`
  - `dashboard_runtime_loader_contracts.py`
  - `dashboard_runtime_loader_dependencies.py`
  - `dashboard_runtime_loaders.py`
  - `dashboard_server_contracts.py`
  - `dashboard_server_dependencies.py`
  - `dashboard_server.py`
  - `runtime.py`
  - `runtime_lifecycle.py`
- Normalized `meshdash/runtime_types.py` callback aliases from broad `Any` to `object`/typed built-in generics, eliminating remaining `Any` usage in `dashboard_*` / `runtime*` modules.
- Tightened tracker snapshot/runtime state contracts to concrete typed row/counter/iterable boundaries:
  - `tracker_snapshot_build_contracts.py`
  - `tracker_snapshot.py`
  - `tracker_runtime_state.py`
  - `tracker_runtime_types.py`
  - `tracker_snapshot_contracts.py`
  - `tracker_storage_contracts.py`
- Tightened chat/packet entry helper signatures from broad `Any` to typed object+callback contracts:
  - `chat_entry.py`
  - `tracker_entries.py`
- Tightened history read/query contract surfaces (protocols + loaders + analytics helpers):
  - `history_read_contracts.py`
  - `history_read_api.py`
  - `history_read_history.py`
  - `history_queries.py`
  - `history_readers.py`
  - `history_node_analytics.py`
  - `history_online_analytics.py`
- `runtime_state_loader` now accepts `RevisionInfo` and performs dict conversion at the state-payload boundary.
- Reused shared HTTP route type aliases across API domain modules (`api_system`, `api_chat`, `api_history_node`, `api_history_online`) to reduce duplicated callable signatures.
- Added shared HTTP handler protocol contracts in `meshdash/http_handler_contracts.py` and applied them across API/route/response dispatch modules (`api_chat`, `api_system`, `http_routes_*`, `http_api_*`, `http_responses`, `http_handler`) so HTTP boundaries no longer rely on raw `Any` handler typing.
- Added tracker runtime-init protocol contracts in `meshdash/tracker_runtime_init_contracts.py` and applied them across tracker constructor/setup wiring (`tracker_runtime_init.py`, `tracker_setup.py`) so startup dependency boundaries use explicit contracts instead of raw `Any`.
- Added tracker bootstrap protocol contracts in `meshdash/tracker_bootstrap_contracts.py` and applied them to bootstrap/init wiring (`tracker_bootstrap.py`, `tracker_setup.py`, `tracker_runtime_init_contracts.py`) so history-store bootstrap expectations are explicitly typed.
- Added tracker storage protocol contracts in `meshdash/tracker_storage_contracts.py` and applied them to packet runtime dependency/dataclass wiring (`tracker_storage.py`, `tracker_runtime_packet_contracts.py`, `tracker_runtime_record.py`, `tracker_runtime_record_dependencies.py`) so receive-path storage surfaces no longer rely on raw `Any` for buffers/history writes.
- Added tracker seed protocol contracts in `meshdash/tracker_seed_contracts.py` and applied them to seed/receive binding entrypoints (`tracker_seed.py`, `tracker_runtime_receive_bindings.py`) to reduce top-level runtime `Any` surfaces around tracker bootstrap packet replay.
- Tightened tracker receive/record interface typing (`tracker_runtime_receive.py`, `tracker_runtime_record.py`) by replacing raw `Any` interface surfaces with `object` where no concrete interface API is consumed.
- Tightened node-id resolver identity surfaces (`tracker_node_resolver.py`, `nodes_identity.py`, `runtime_types.py`) so interface/node-number callback contracts use explicit `object` inputs instead of raw `Any`.
- Unified tracker history-store runtime typing in `tracker_runtime_types.py` / `tracker_runtime_init_contracts.py` so receive/snapshot/init paths share a combined `TrackerRuntimeHistoryStore` contract instead of parallel store aliases.
- Added local-chat runtime protocol contracts in `meshdash/tracker_local_chat_contracts.py` and applied them through `tracker_local_entry.py`, `tracker_local_chat.py`, and `tracker_runtime_chat.py` so local chat append/build/runtime-state surfaces are explicitly typed.
- Added send-path protocol contracts in `meshdash/send_chat_contracts.py` and applied them through `runtime_send_contracts.py`, `runtime_send_dependencies.py`, `runtime_send_loader.py`, and `services_chat.py` so send interface/lock dependency boundaries are explicitly typed.
- Tightened tracker receive/record runtime callback contracts in `meshdash/runtime_types.py` by replacing broad callback aliases with explicit protocol signatures for packet recorders, receive dispatch, and node-id resolution callbacks.
- Tightened tracker observation/delivery callback contracts in `meshdash/runtime_types.py` with explicit protocol signatures for delivery-update extraction, delivery-state updates, routing-delivery application, and direct-edge observation callbacks; applied those shared contracts in `tracker_observation.py` and `tracker_delivery.py`.
- Tightened tracker parse/process callback contracts in `meshdash/runtime_types.py` with explicit protocol signatures for packet parsing and parsed-packet processing collaborators used by receive/runtime record wiring.
- Tightened tracker artifact/storage callback contracts in `meshdash/runtime_types.py` with explicit protocol signatures for packet summary/chat-entry builders, packet artifact assembly, and storage-update callbacks; aligned `tracker_receive.py` to typed recent-buffer/history-writer callback surfaces.
- Unified tracker runtime/snapshot port-counter typing behind a shared `PortCounter` protocol in `runtime_types.py` (supports mutation + `most_common()`); applied across receive/record/snapshot contracts (`tracker_snapshot_build_contracts.py`, `tracker_observation.py`, `tracker_receive.py`, `tracker_runtime_packet_contracts.py`, `tracker_runtime_record.py`, `tracker_runtime_record_dependencies.py`) to match actual parsed-packet and snapshot behavior.
- Removed the receive-path legacy dependency dict shim by adding `record_tracker_packet_unlocked_from_dependencies(...)` in `meshdash/tracker_runtime_receive_dependencies.py`; `tracker_runtime_receive.py` now forwards typed dependency objects directly to legacy callbacks.
- Added typed tracker packet-ingest dependency contract:
  - `TrackerPacketRuntimeDependencies` in `meshdash/tracker_runtime_packet_contracts.py`
  - `record_tracker_packet_unlocked_with_dependencies(...)` in `meshdash/tracker_runtime_record.py`
  - `tracker_runtime_receive` now routes through the typed path by default while preserving legacy callback override compatibility.
  - `tracker_runtime_receive_dependencies.py` now centralizes dependency assembly and legacy kwargs mapping for receive-path compatibility.
  - `tracker_runtime_record_dependencies.py` now centralizes legacy-arg to typed-dependency mapping for tracker record compatibility.
  - existing `record_tracker_packet_unlocked(...)` preserved as compatibility wrapper.
- Added typed chat-send runtime dependency contract:
  - `SendChatRuntimeDependencies` in `meshdash/runtime_send_contracts.py`
  - `build_send_chat_runtime_dependencies_from_legacy_args(...)` in `meshdash/runtime_send_dependencies.py`
  - `build_send_chat_loader_with_dependencies(...)` in `meshdash/runtime_send_loader.py`
  - existing `build_send_chat_loader(...)` preserved as compatibility wrapper.
- Added typed state-snapshot runtime dependency contract:
  - `StateSnapshotRuntimeDependencies` in `meshdash/runtime_state_contracts.py`
  - `build_state_snapshot_runtime_dependencies_from_legacy_args(...)` in `meshdash/runtime_state_dependencies.py`
  - `build_state_snapshot_loader_with_dependencies(...)` in `meshdash/runtime_state_loader.py`
  - existing `build_state_snapshot_loader(...)` preserved as compatibility wrapper.
- Added typed dashboard-loader assembly dependency contract:
  - `DashboardRuntimeLoaderDependencies` in `meshdash/dashboard_runtime_loader_contracts.py`
  - `build_dashboard_runtime_loader_dependencies_from_legacy_args(...)` in `meshdash/dashboard_runtime_loader_dependencies.py`
  - `build_dashboard_runtime_loaders_with_dependencies(...)` in `meshdash/dashboard_runtime_loaders.py`
  - existing `build_dashboard_runtime_loaders(...)` preserved as compatibility wrapper.
- `build_dashboard_runtime_context(...)` now routes through the typed dashboard-loader dependency path by default while preserving legacy loader injection override compatibility.
- Applied shared runtime callback aliases in `meshdash/wiring_adapters.py` so state/reaction/local-node/http adapter wrappers use the same contract vocabulary as runtime wiring.
- Applied shared runtime callback aliases in `meshdash/tracker_callbacks.py` (delivery callback bundle + timeout/clock parsers) to reduce ad-hoc callable typing in tracker runtime wiring.
- Applied shared runtime callback aliases in `meshdash/dashboard_server.py`, `meshdash/dashboard_runner_impl.py`, and `meshdash/wiring_runtime.py` to reduce remaining ad-hoc runtime/server callable signatures.
- Normalized remaining shared callable aliases in utility/state surfaces (`meshdash/nodes_identity.py`, `meshdash/mesh_ops.py`, `meshdash/state_service.py`) to use `runtime_types` contracts.
- Completed a broad `Any`-removal pass across `meshdash/*.py` helper/runtime modules (tracker ingest/record/receive, history write/read helpers, HTTP helpers, chat send/delivery helpers, node/time/disk/theme utilities), reducing remaining `Any` references in `meshdash` to zero while preserving behavior.
- Added typed dashboard-server dependency contract:
  - `DashboardServerDependencies` in `meshdash/dashboard_server_contracts.py`
  - `build_dashboard_server_dependencies_from_legacy_args(...)` in `meshdash/dashboard_server_dependencies.py`
  - `build_dashboard_server_with_dependencies(...)` in `meshdash/dashboard_server.py`
  - existing `build_dashboard_server(...)` preserved as compatibility wrapper.
- State summary/revision flow now accepts typed `RevisionInfo` through runtime state loading while preserving dict compatibility at the state/summary payload boundary.
- `meshdash/services_chat.py` now uses shared runtime callable aliases for reaction/local-node/time and chat normalization callbacks (no remaining ad-hoc `Callable[..., Any]` in runtime-adjacent modules).
- Added typed node-collection contract for state assembly:
  - `CollectedNodes` + `coerce_collected_nodes(...)` in `meshdash/state_node_contracts.py`
  - `collect_nodes_typed(...)` in `meshdash/state_node_rows.py` with legacy dict wrapper preserved
  - `state_service` now consumes the typed node contract internally while accepting legacy mapping-shaped injections in tests/callers.
- Added typed tracker-snapshot contract for state fanout:
  - `TrackerSnapshot` + `coerce_tracker_snapshot(...)` in `meshdash/tracker_snapshot_contracts.py`
  - `build_tracker_snapshot_payload_typed(...)` in `meshdash/tracker_snapshot.py` with legacy dict wrapper preserved
  - `build_tracker_snapshot_typed(...)` / `build_tracker_snapshot_for_tracker_typed(...)` in `meshdash/tracker_runtime_state.py` with existing dict-return APIs preserved
  - `DashboardTracker.snapshot_typed(...)` in `meshdash/tracker_runtime_impl.py` while `snapshot(...)` remains dict-compatible
  - `state_service` and `state_summary` now consume typed tracker snapshot contracts internally while accepting legacy mapping-shaped payloads.
- Added tracker snapshot assembly protocol contracts in `meshdash/tracker_snapshot_build_contracts.py` and applied them through `tracker_snapshot.py`, `tracker_runtime_state.py`, and `tracker_runtime_types.py` so snapshot/store callback boundaries use explicit typed protocols instead of raw `Any`.
- Added explicit tracker collaborator protocols for service/runtime boundaries:
  - `StateTracker` protocol in `meshdash/state_service_contracts.py` for `/api/state` service dependencies
  - `TrackerSnapshotRuntimeState` protocol in `meshdash/tracker_runtime_types.py` for snapshot assembly helpers.
- Added `meshdash/state_service_contracts.py` to centralize state assembly collaborator callback aliases (`collect_nodes`, local-state safe collection, summary builder, redaction, revision payload).
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
