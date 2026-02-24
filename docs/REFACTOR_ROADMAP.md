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

### Steps

1. Create `meshdash/state/service.py` for:
   - snapshot state shape
   - node/chat/packet projections
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

### Steps

1. JSON theme schema (light/dark token maps).
2. Safe validation + fallback to defaults.
3. Settings endpoint + local persistence.

### Exit criteria

- Users can switch palette presets at runtime.
- Default theme remains the stable baseline.
