# Python Plugin Security Review

Date: 2026-07-23
Scope: the alpha Python plugin runtime, package discovery, administration UI and
HTTP endpoints, persisted state, radio actions, file transfer integration, and
deployment defaults.

Update: 2026-07-25. The post-review console bridge, route toggles, README
viewer, and mesh-access indicator are covered by this document.

## Executive conclusion

No stop-ship security issue remains under the selected threat model:
single-user, administrator-installed, trusted local plugin code; untrusted mesh
input; and dashboard UI administration that may cross a trusted LAN, VPN, or
reverse proxy.

The hardening preserves the ordinary local development workflow. New local
plugins start disabled, but a previously enabled plugin continues after its
files are edited and Meshyface restarts. Compatible settings carry forward
automatically, while active conversations are cleared on a package change. A
same-origin browser session can inspect, configure, and enable plugins without
a separate API token prompt. External API-style write clients still use the
configured API token. The main controls validate untrusted mesh input and host
actions, and bound runtime, state, radio, file-transfer, and restart behavior.

This is not a hostile-plugin sandbox. An enabled plugin is arbitrary Python
running as the Meshyface service user. It can read that user's files, access the
network, import shared dependencies, start subprocesses, and deliberately
interfere with the host process. Internet-facing or third-party marketplace
plugins require a materially stronger isolation design.

Meshyface intentionally preserves a low-friction local plugin development loop.
The manifest carries identity, entrypoint, command, view, setting, and
enablement metadata that the host actually uses. It does not carry advisory
capability labels because non-enforced author claims would be easy to
misinterpret as a security boundary.

## Threat model

The implemented controls defend against:

- unauthenticated remote or cross-origin plugin administration;
- accidental disclosure of plugin settings, debug records, and file jobs in
  the public dashboard state;
- stale browser tabs mutating a different package revision than the one shown;
- malformed packages disrupting discovery of healthy packages;
- symlink, special-file, and conventional owner/mode trust mistakes;
- runaway state, sessions, action batches, radio use, worker restarts, and file
  transfers;
- malformed or nonfinite packet fields and cross-peer/channel session or state
  confusion from untrusted mesh traffic;
- forged file-transfer acknowledgements, unbounded inbound ACK solicitation,
  and path-swap races;
- terminal control-sequence injection through plugin debug output; and
- shell metacharacters in deployment plugin paths and lists.

The controls do not defend against:

- malicious or carelessly changed local plugin code running as the service
  user;
- a malicious dependency in Meshyface's shared Python environment;
- an administrator/root or same-UID writer;
- runtime behavior derived from excluded VCS, cache, or coverage artifacts;
- write-granting extended filesystem ACLs;
- compromise through an unrelated same-origin dashboard XSS;
- plaintext network interception when HTTP is used without TLS; or
- denial of service that deliberately uses unrestricted Python, subprocesses,
  memory, or host filesystem access.

## Plugin author input rules

All mesh-derived fields are hostile input: message text, sender and destination
IDs, decoded packet fields, node metadata, file-transfer metadata, and
mesh-derived values in node snapshots. Host normalization and JSON framing make
those fields bounded and structurally safe to transport; they do not make the
contents trustworthy. Plugin authors must not pass them to `eval`/`exec`,
interpolate them into `shell=True` or other command strings, concatenate them
into SQL, or use them as filesystem paths without strict validation,
allowlisting, and confinement. Use fixed argument vectors, parameterized SQL,
canonical identifiers, and host-brokered file operations.

The spawned worker is fault and timeout containment for trusted local source.
It is not an operating-system sandbox and does not make unsafe use of hostile
mesh data safe.

## Findings and disposition

### Administration and privacy

Status: fixed.

- Plugin mutation endpoints and the detailed plugin status endpoint follow the
  dashboard UI access model.
- Browser writes require `application/json` and reject cross-origin requests.
- `/api/state` exposes only plugin health, counts, and display tickers.
  Installed-package details, saved settings, debug records, worker details, and
  file jobs moved behind `/api/admin/plugins`.
- Failing a privileged refresh blurs and closes settings forms, clears
  drafts/debug/admin objects, and replaces privileged DOM content immediately.
- Package mutations include the digest that was rendered with the form or
  button. A stale identity is rejected with HTTP 409, and stale drafts are
  discarded.
- Dashboard HTML now denies cross-origin framing to reduce clickjacking.

Residual: use a TLS reverse proxy or trusted tunnel for administration from
another machine. Saved text settings are returned to the authorized DOM for
editing and are not a write-only secret type. Settings, debug records, and
plugin state are secret-bearing but are not encrypted at rest.

### Package fingerprint and discovery

Status: fixed for the trusted local-package model.

- Local plugin IDs with no stored enablement record cannot self-enable through
  `default_enabled = true`.
- Once a local plugin is enabled, that operator choice persists by plugin ID
  across package edits and restarts. This is deliberate for single-user local
  development: the hacking loop is edit, restart, and test, with no reapproval
  for a known plugin.
- A plugin ID is a durable local trust/configuration namespace. Deleting a
  package does not erase it; unrelated code later installed under the same ID
  inherits the prior enabled/disabled choice and may inherit schema-compatible
  settings plus global and peer state. Use a new ID or clear the old persisted
  records when the code is not a continuation of the same plugin.
- A `sha256:` fingerprint covers operational package files and remains visible
  in the admin view. Enable/configure mutations carry the fingerprint rendered
  with their controls, so a stale revision receives HTTP 409 and refreshes.
- Common development-only paths are excluded from the fingerprint and package
  limits: `.git`, `.hg`, `.svn`, `__pycache__`, `.pytest_cache`, `.mypy_cache`,
  `.ruff_cache`, `htmlcov`, and `.coverage`. This permits a live local checkout
  without fingerprint churn from tooling metadata.
- The worker recomputes the package digest before import and does not write
  Python bytecode into the plugin package.
- Symlinks, special files, unrelated owners, world-writable files, and
  shared-group-writable files are rejected. A service user's private primary
  group remains supported even when the process uses a shared effective group
  such as `dialout`.
- Manifest reads use no-follow, nonblocking regular-file descriptors and
  recheck mutation during inspection.
- Malformed packages, invalid UTF-8 filenames, and entrypoint symlink loops are
  isolated as per-package discovery errors.
- Defensive limits cover manifest bytes, discovered packages, root/package
  entries, commands, and total package bytes.
- A fatal startup package is quarantined for that package identity so it cannot
  periodically crash the shared worker. Editing still requires a restart
  because filesystem hot reload is not supported; a previously enabled plugin
  resumes on the newly discovered fingerprint.

Residual: the fingerprint is diagnostic identity, not publisher provenance or
a hostile-code boundary. Excluded development paths and shared Python
dependencies are outside it, and trusted plugin code can read them. Conventional
POSIX owner/mode bits are checked, but extended ACLs are not; remove
write-granting ACLs and keep the discovery root and its parents
administrator-controlled.

### Mesh access indicator

Status: documented as a best-effort review hint.

- The Scripts workspace shows the worker's detected Mesh access classification:
  `Detected Write`, `Detected Read`, `No Mesh Detected`, or `Unknown`.
- The indicator is computed from registered handlers and bytecode after the
  trusted script is loaded. It is not manifest-authored and not a policy gate.
- Route toggles remain the enforcement point for Mesh, Console, Ticker, and
  View delivery.
- The manifest intentionally has no optional `capabilities` field. A future
  capability model should be enforced at the SDK/host boundary before it is
  presented as a security signal.

Residual: the detector can miss helper-module or dynamic behavior and can
over-classify broad handler access. Treat it as a quick review hint, not as a
hostile-code boundary.

### State, settings, and sessions

Status: fixed.

- Peer state and conversations are keyed by channel as well as plugin, peer,
  and local node where applicable. Legacy rows migrate to channel 0.
- No-op state is not rewritten, cleared peer rows are deleted, and per-plugin
  limits cap peer rows, peer JSON bytes, and active sessions.
- Enablement persists by plugin ID across a trusted local package edit.
- Compatible saved settings carry forward automatically after a package
  fingerprint change. Incompatible values are withheld and manifest defaults
  are used until the administrator saves replacements.
- Active sessions are cleared when the package fingerprint changes.
- Global and peer state deliberately survive a version change for application
  continuity.

Residual: plugin state is not a secret vault. Enabled code runs as the same OS
user and can read the SQLite files directly.

### Runtime, radio, and lifecycle containment

Status: fixed for accidental and malformed behavior.

- Worker/event/control/action queues and protocol frames are bounded.
- Handler timeouts terminate the worker; startup retries use exponential
  backoff; repeated handler failures receive temporary backoff.
- One handler result may schedule at most 64 synchronous radio frames, avoiding
  multi-minute monopolization by groups of maximum long replies.
- Per-plugin and global one-minute radio frame/byte budgets include segmented
  replies, text sends, worst-case outbound file retries, and the reservation
  made when a plugin accepts an inbound offer.
- The inbound transfer service independently limits acknowledgement traffic to
  64 frames per sender and 128 frames globally in any rolling 60-second window,
  covering metadata, progress, completion, and duplicate-chunk ACK paths.
- File transfer jobs are asynchronous and cannot exceed their admitted frame
  ceiling.
- Reserved/broadcast node IDs are rejected for direct text and file actions.
- Nonfinite radio metadata and malformed endpoint IDs are dropped or normalized
  instead of escaping packet callbacks.
- Terminal debug output renders control characters visibly, preventing
  ANSI/OSC injection and forged multiline logs.

Residual: enabled plugins share one worker, so a crashing or hanging plugin can
briefly disrupt healthy plugins before supervision/quarantine takes effect.
There is no hostile-code CPU, memory, process-tree, filesystem, or network
sandbox, and subprocess descendants can outlive a worker-only restart.

### File transfer

Status: fixed.

- Approved files are opened relative to trusted directory descriptors with
  no-follow semantics, regular-file checks, and bounded reads, closing
  check/open path-swap races.
- ACK and flow-control frames are bound to the original peer, channel, and
  local destination.
- Cost estimates include retry ceilings and are enforced during transmission.
- Transit packet hooks remain available for monitoring plugins, but that broad
  packet visibility is now documented as an enabled capability.

Residual: Meshtastic sender IDs and channel membership are not cryptographic
identity. Allow lists and peer/channel binding prevent accidental
cross-transfer control but cannot make a spoofable radio transport strongly
authenticated. The inbound service applies replay limits and an ACK cooldown,
then enforces its own sender/global rolling ACK ceiling rather than the
runtime's per-plugin accounting. File transfer also remains intentionally
airtime-intensive.

### Deployment defaults

Status: hardened.

- Remote deployment validates single-line plugin settings and shell-quotes all
  plugin-related paths before the SSH `mkdir` command.
- Compose drops Linux capabilities, enables `no-new-privileges`, and sets a PID
  ceiling.
- systemd enables `NoNewPrivileges`, `PrivateTmp`, a read-only protected system
  tree, kernel/control-group protections, SUID/SGID and personality
  restrictions, and an empty capability bounding set.

Residual: the Compose service still runs as container UID 0 and systemd does
not impose plugin-specific memory/CPU limits. These settings reduce host attack
surface but do not make hostile Python safe.

## Compatibility and operational impact

- Normal direct localhost use remains tokenless.
- Trusted LAN, VPN, hostname, and proxy dashboard use follows the same-origin
  browser access model. External API-style write clients need an API token when
  one is configured; untrusted networks additionally need TLS or an SSH tunnel.
- Local plugin IDs without stored enablement start disabled. Previously enabled
  local plugin IDs continue after an edit and restart, and compatible saved
  settings carry automatically.
- Reusing an old ID for unrelated code also reuses its enabled/disabled choice
  and may reuse compatible settings plus global and peer state. Choose a new ID
  or clear the old persisted records for an unrelated replacement.
- Package changes still require a restart because there is no filesystem hot
  reload. No repeated enablement confirmation is required.
- Development VCS/cache/coverage artifacts do not affect the fingerprint or
  package limits; operational package files do.
- Active conversational sessions clear on a fingerprint change; global and
  peer state continue.
- Ordinary enable/disable and configuration changes remain live.
- The Mesh access badge is best-effort display only. It does not change routing
  or plugin execution behavior.
- Cross-origin iframe embedding is intentionally blocked; direct use and
  same-origin embedding still work.
- Limits affect pathological packages or behavior, not the normal SDK surface:
  64 discovered plugins, 1,024 package entries, 64 MiB/package, 64 commands,
  512 peer-state rows, 8 MiB peer-state JSON, and 256 sessions per plugin.

## Verification

- Current local cleanup verification on 2026-07-29:
  - Ruff passed.
  - `git diff --check` passed.
  - Focused workspace, Zork docs, scripts docs, admin route, publication-readiness,
    and coverage-report slice: 78 passed.
  - Full virtualenv suite: 1,329 passed and 3 browser-dependent tests skipped.
  - Local coverage gate: 1,329 passed, 3 skipped, and 88.74% coverage against
    an 85% requirement.

The repository coverage wrapper uses `python` from `PATH`. On this development
workstation, the default `/usr/bin/python` lacks the installed `meshtastic`
dependency, so the successful coverage gate was run with the project virtualenv
first in `PATH`. The GUI responsiveness benchmark was attempted, but
`scripts/run_gui_responsiveness_local.sh` refused to run because an existing
dashboard was serving on `127.0.0.1:8877`; stop that dashboard and rerun the
benchmark before pushing or opening the PR.

## Deployment recommendation

For the intended setup, bind the dashboard to loopback whenever practical. For
LAN/VPN dashboard access, restrict the listening interface and firewall, and use
TLS or an SSH tunnel across untrusted links. Set a strong API token for external
API-style write clients. Keep plugin packages administrator-controlled; use the
displayed fingerprint for change visibility and troubleshooting.

Do not expose this alpha trusted-code plugin system directly to the public
Internet. If future use includes third-party or marketplace code, the next
security boundary should be per-plugin OS/container isolation with restricted
filesystem/network access, signed provenance, isolated dependency environments,
and a brokered secret API.
