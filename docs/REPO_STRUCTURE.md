# Repository Structure

## Active Surface

- `mesh_dashboard.py`: main dashboard web app and API server.
- `mesh_connection.py`: Meshtastic serial/TCP connection abstraction.
- `meshdash/chat.py`: chat-entry and delivery-state transition helpers.
- `meshdash/chat_send.py`: chat send/reaction payload normalization, validation, and response builders.
- `meshdash/config.py`: centralized dashboard defaults/constants and sensitive-key policy.
- `meshdash/app_meta.py`: environment/version/commit metadata assembly helpers.
- `meshdash/api_inputs.py`: shared API query/body parsing and request-size validation helpers.
- `meshdash/cli.py`: CLI parser/bootstrap argument definitions and env default resolution.
- `meshdash/dashboard_runtime.py`: dashboard runtime orchestration and server lifecycle.
- `meshdash/html.py`: extracted dashboard HTML renderer and frontend template.
- `meshdash/helpers.py`: extracted pure utility helpers used by runtime and tests.
- `meshdash/history_store.py`: extracted SQLite history persistence/rollup store.
- `meshdash/history_readers.py`: row-to-payload decoders for recent packets/chat/connections reads.
- `meshdash/history_rollups.py`: metric rollup math helpers shared by history persistence paths.
- `meshdash/history_views.py`: node history/online activity empty payload and loader builders.
- `meshdash/http_api.py`: extracted HTTP handler factory for dashboard API routes.
- `meshdash/http_responses.py`: shared HTTP response emitters for JSON/HTML/text.
- `meshdash/mesh_ops.py`: Meshtastic/protobuf-specific packet send and local node-id helpers.
- `meshdash/nodes.py`: extracted node/interface/time utilities for dashboard runtime.
- `meshdash/revision.py`: revision/version/git metadata helpers for header build info.
- `meshdash/runtime.py`: startup/runtime networking + default gateway helpers.
- `meshdash/runtime_callbacks.py`: runtime closure builders for state snapshots and chat send actions.
- `meshdash/runtime_lifecycle.py`: startup status output, serve-loop interrupt handling, and shutdown cleanup helpers.
- `meshdash/services.py`: shared history/online loader builders, chat-send service logic, and empty payload helpers.
- `meshdash/state.py`: node/local snapshot + assembled `/api/state` payload helpers.
- `meshdash/state_nodes.py`: node/local snapshot collection helpers extracted from state assembly.
- `meshdash/state_summary.py`: summary/local-state enrichment helpers for `/api/state`.
- `meshdash/tracker.py`: extracted packet/chat tracking, edge synthesis, snapshots, and seed-from-node-db helper.
- `meshdash/theme.py`: centralized light/dark theme tokens and CSS builder.
- `meshdash/wiring.py`: dependency checks and runtime wiring assembly for dashboard startup.
- `meshtastic-dashboard.service`: systemd unit template for VM deployment.
- `README.md`: setup, deploy loop, and operations.
- `docs/PROJECT_PLAN.md`: product direction and phased roadmap.
- `docs/REFACTOR_ROADMAP.md`: modularization plan for incremental refactor.
- `tests/`: pytest coverage for core helper behavior.

## Archive Surface

- `archive/scripts/`: legacy utility scripts no longer part of active runtime.
- `archive/services/`: archived service units not used by dashboard server.
- `archive/docs/`: older setup references retained for historical context.

## Conventions

- Keep dashboard runtime entrypoint stable (`mesh_dashboard.py`).
- Prefer adding pure helper functions for new logic to improve testability.
- Any script not used by dashboard runtime belongs in `archive/`.
- Every substantial feature should include:
  - tests in `tests/`
  - docs update in `README.md` or `docs/`
