# Repository Structure

## Active Surface

- `mesh_dashboard.py`: main dashboard web app and API server.
- `mesh_connection.py`: Meshtastic serial/TCP connection abstraction.
- `meshdash/chat.py`: chat-entry and delivery-state transition helpers.
- `meshdash/html.py`: extracted dashboard HTML renderer and frontend template.
- `meshdash/helpers.py`: extracted pure utility helpers used by runtime and tests.
- `meshdash/http_api.py`: extracted HTTP handler factory for dashboard API routes.
- `meshdash/nodes.py`: extracted node/interface/time utilities for dashboard runtime.
- `meshdash/revision.py`: revision/version/git metadata helpers for header build info.
- `meshdash/runtime.py`: startup/runtime networking + default gateway helpers.
- `meshdash/services.py`: shared history/online loader builders, chat-send service logic, and empty payload helpers.
- `meshdash/state.py`: node/local snapshot + assembled `/api/state` payload helpers.
- `meshdash/theme.py`: centralized light/dark theme tokens and CSS builder.
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
