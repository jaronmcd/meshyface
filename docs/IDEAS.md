# Ideas Backlog

- sort out click selection, map non map



- bot activity show as (1)

- ask if we can make github issues and use them?

- theme settings tab

- put channels in tabs w/ notifaction totalss (N)

- make our chats look differant
- at the base level, report to other users the version of meshyface


## PotatoMesh Learnings

- Quick win: add optional API token auth mode for write endpoints (chat send/settings apply) so WAN/VPN deployments are safer.
- Quick win: add a `PRIVATE_MODE` toggle to hide/disable public chat and message APIs for sensitive deployments.
- Quick win: add `/api/version` and `/api/health` endpoints for easier remote ops checks.
- Quick win: expose Prometheus-style metrics endpoint (`/metrics`) for packet rate, node count, poll errors, and radio link status.
- Medium: split ingest from UI process so multiple remote radios can feed one Meshyface instance without direct USB attachment.
- Medium: add ingestor identity/heartbeat table and UI panel ("which feeds are alive, last seen, packet volume").
- Medium: add allowed/hidden channel filters at ingest edge to reduce clutter and protect sensitive channels.
- Bigger bet: optional federation mode (instance directory + peer discovery + staleness pruning) while keeping default local-first.
- Bigger bet: region/community profile in UI (site name, channel/frequency label, map center, contact link) via env vars.
- Guardrail: keep Meshyface chat-first UX; borrow backend/ops patterns from PotatoMesh without adopting its full product direction.
