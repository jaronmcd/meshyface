# Ideas Backlog


- fix bug in games that causes a stand still


- allow public bot shutdown with opt in


- can you make it so a #hashtag trends in puiblic chat creates channels? After X amount of the same #'s (we will start with 1) that will start a "channel", adding clickable icons below peer to peer, then when the channel is selected, the view is filtered to messages with the #, and the # is trimmed if it's at the end of the message to keep the view clean, if its in the middle of the message the # is stripped off and the treandy word is kept to keep it natual. And when someone transmits from the view # is auto tagged at the end, and if they type the # it stripped to prevent duplicates. Then for now a channel will timeout and be removed after 10 minutes of activity. What's cool is people can setup tx channels for private chat on  a #, but still keep the chat view to all to see the pubic chat alongside.



- bot activity show as (1)
- at the base level, report to other users the version of meshyface
- fix deselected channel notifaction
- put channels in tabs w/ notifaction totalss (N)

- make our chats look differant

- add node ID
- Ability to send a direct message by manually entering a Node ID (when only the Node ID is known).
- Ability to add a favorite by manually entering a Node ID.

- what are directed links and can we show more about them?



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
