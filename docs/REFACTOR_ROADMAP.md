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
- Added targeted tests:
  - `tests/test_history_store_runtime_init.py`
  - `tests/test_history_store_runtime_maintenance.py`

### Steps

1. `meshdash/history/db.py` (connection + schema)
2. `meshdash/history/packets.py`
3. `meshdash/history/chat.py`
4. `meshdash/history/nodes.py`

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
- Added `meshdash/api_chat.py` for `/api/chat/send` POST domain handling.
- `meshdash/http_routes_get.py` now delegates domain payload/response logic into those modules.
- `meshdash/http_routes_post.py` now delegates chat-send behavior into `api_chat`.
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

### Steps

1. Consider stricter type aliases/protocols for callback signatures used in runtime wiring.
2. Triage remaining dict-shaped payloads where they represent transport formats vs internal contracts.

### Exit criteria

- Runtime orchestration uses typed object contracts for core boot/server handoff.
- Fewer string-key regressions during future refactors.
