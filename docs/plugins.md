# Plugins and Script API (Alpha)

Meshyface can run administrator-installed Python plugins in a spawned worker.
Each plugin is an installed, versioned package that currently exports one
executable `Script`. The runtime is enabled by default, so its management surface
is shown as **Apps → Scripts (Alpha)**, where an administrator can inspect installed
plugins, inspect their scripts, save plugin enablement changes, and edit any
configuration fields declared by their manifests.

The word **Alpha** describes this management UI. Plugins use the versioned
`api_version = 1` host/worker protocol. Package discovery and administration use
plugin terminology (`--plugins-*` and `MESH_DASH_PLUGINS_*`), while executable
author code uses the Script API from `meshdash.plugins`.

## Trust And Isolation

Script Python is fully trusted administrator code. It runs as the same
operating system user as Meshyface and may import installed packages, read or
write files, open network connections, and start subprocesses. The worker
boundary contains ordinary exceptions and infinite handlers; it is not a
security sandbox and does not defend against hostile code, resource exhaustion,
or deliberate process signaling.

The package fingerprint is a change-detection and stale-request signal, not a
hostile-code security boundary or publisher signature. It covers operational
files in the plugin package. Common local-development metadata and generated
artifacts are excluded from both the fingerprint and package limits:
`.git`, `.hg`, `.svn`, `__pycache__`, `.pytest_cache`, `.mypy_cache`,
`.ruff_cache`, `htmlcov`, and `.coverage`. Those excluded paths are
intentionally outside the integrity signal, so plugins must not depend on them
for runtime code or configuration. Other package files remain fingerprinted
and count toward package limits. This keeps an ordinary live local checkout
usable while making meaningful package changes visible.

Dependencies installed into Meshyface's shared Python environment are
host-level trusted code and are also outside the package fingerprint. Pin and
manage them as part of the local Meshyface installation.

The Scripts workspace shows a best-effort Mesh access badge derived from the
loaded script's registered handlers and bytecode. It is an operational hint,
not a manifest-declared promise, policy gate, or sandbox.

Meshyface does not pass the live radio, tracker, HTTP server, SQLite connection,
or internal locks to a script. Events, state snapshots, and requested actions
cross the worker boundary as strictly validated JSON bytes.

Treat every mesh-derived value as hostile input, including message text,
sender/destination IDs, packet fields, node metadata, file-transfer metadata,
and values returned through node snapshots. Normalization makes those values
bounded and JSON-safe; it does not make their contents trustworthy. Plugin code
must not pass them to `eval`/`exec`, interpolate them into `shell=True` or other
command strings, concatenate them into SQL, or use them as filesystem paths
without a strict allowlist and confinement check. Prefer fixed argument
vectors, parameterized SQL, canonical node-ID validation, and host-brokered file
operations. The worker provides fault and timeout containment, not an operating
system sandbox; local plugin source remains fully trusted.

## Try The Hello Reference Plugin With One Restart

The repository includes a minimal bundled reference plugin at
`meshdash/included_plugins/hello`. Bundled plugins are discovered independently
of the configurable local plugin directory, so start or restart Meshyface once
with the reference plugin enabled:

```bash
python mesh_dashboard.py --plugin-enable hello
```

Keep the rest of the arguments required by your radio and HTTP setup. If a
dashboard is already running, add these options to its normal service command
and restart that service instead of launching a second dashboard. Open
**Apps → Scripts (Alpha)** and confirm that **Hello** is running, then send
`!hello` on the mesh. The reply count is stored separately for each sender.

For a container installation, set `MESH_DASH_PLUGIN_ENABLE=hello` before
recreating the container. The bundled plugin already ships in the image.
Standard systemd deployments also include it, so no plugin copy step is
required.

Additional bundled reference plugins are available under
`meshdash/included_plugins/`.
`packet_city` demonstrates packet handlers and dashboard tickers, while `zork`
demonstrates long replies, peer-specific interactive gameplay, and the local
Console command bridge.

## Runtime Configuration

The end-to-end master switch is on by default:

```bash
python mesh_dashboard.py --no-plugins-enable
```

The equivalent environment setting is:

```bash
MESH_DASH_PLUGINS_ENABLE=false
```

`--plugins-enable` overrides a disabled environment default. When the master
switch is off, Meshyface hides the Scripts workspace and does not discover
plugins, open script state, start a worker or dispatcher, route messages,
restore sessions, or execute script actions. Normal dashboard messaging and all
non-script services remain active.

Relevant startup options are:

- `--plugins-directory PATH`: persistent local plugin package directory.
- `--plugins-state-db PATH`: independent state, session, and enablement database.
- `--plugins-files-directory PATH`: approved root for script-requested file sends.
- `--plugins-handler-timeout SECONDS`: handler deadline before worker restart.
- `--plugins-event-queue-size COUNT`: bounded pending-event capacity.
- `--plugin-enable ID` and `--plugin-disable ID`: repeatable per-plugin overrides.

The path options also accept `MESH_DASH_PLUGINS_DIRECTORY`,
`MESH_DASH_PLUGINS_STATE_DB`, and `MESH_DASH_PLUGINS_FILES_DIRECTORY`. Initial
per-plugin overrides may be supplied as comma-separated
`MESH_DASH_PLUGIN_ENABLE` and `MESH_DASH_PLUGIN_DISABLE` values.

Individual enablement and Script configuration are persisted when changed in
the Scripts workspace and are not deleted when the master switch is off.
Enablement changes apply live. Configuration changes are visible to the next
handler invocation without restarting the worker.

A newly discovered local plugin ID starts disabled when it has no stored
enablement record, even if its manifest declares `default_enabled = true`. Once
the administrator enables or disables it, that choice persists by plugin ID.
Editing the trusted local package and restarting Meshyface discovers the new
fingerprint and automatically continues running a previously enabled plugin.
The normal hacking loop is edit, restart, and test; there is no reapproval step
for a known plugin.
`--plugin-enable ID` and `MESH_DASH_PLUGIN_ENABLE` can enable a new plugin at
startup, while the corresponding disable override keeps it off.

Treat the plugin ID as a durable local trust and configuration namespace.
Removing a package does not erase that namespace. Installing unrelated code
later under the same ID inherits the prior enabled/disabled choice and may
inherit schema-compatible settings plus global and peer state. Sessions still
clear when the fingerprint changes. Give unrelated replacement code a new ID,
or clear that ID's persisted records (or use a fresh plugin state database)
before installing it.

Enable/configure requests still carry the package fingerprint rendered with
the button or form. If a browser tab is stale because the backend restarted on
a different package revision, Meshyface rejects the request with HTTP 409 and
the workspace refreshes before applying anything.

Saved settings carry forward automatically when they remain valid under the
new manifest schema. If the schema changed incompatibly, the plugin uses its
declared defaults until an administrator saves replacement values. Global and
peer state also persist, while active conversational sessions are cleared when
the package fingerprint changes.

Plugin administration follows the same access model as the dashboard UI. If a
browser can reach the dashboard, the Scripts workspace can inspect and manage
local plugin packages from that same origin. Browser writes must be same-origin
JSON requests, and cross-origin plugin administration is rejected.

For administration from another machine, put Meshyface behind a correctly
configured TLS reverse proxy or reach its listener through a trusted tunnel.
Saved text settings are returned to the Scripts workspace for editing, so treat
that page and its browser session as secret-bearing.

The normal state response exposes only minimal plugin health, counts, active
console command names, and display tickers. Installed-package metadata,
settings, debug records, and file job details are available through the
same dashboard origin via the no-store `/api/admin/plugins` endpoint used by
the Scripts workspace.

The alpha workspace intentionally has no code editor, package installer, or
upload surface. Administrators install and manage trusted local plugin packages
through the filesystem and deployment workflow.

## Plugin Package

Each plugin is one direct child directory containing a manifest and Script entrypoint:

```text
my_script/
    plugin.toml
    script.py
```

Example `plugin.toml`:

```toml
api_version = 1
id = "example"
name = "Example"
version = "1.0.0"
entrypoint = "script.py:script"
commands = ["hello"]
default_enabled = false

[[settings]]
key = "allowed_sender_ids"
label = "Allowed sender IDs"
type = "node_ids"
default = []
description = "Nodes allowed to use this Script."
```

Manifest identity and commands are authoritative. The exported `Script` must match
them exactly. Entrypoints are confined to their plugin directory, duplicate IDs
and commands are rejected, and only enabled entrypoints are imported in the
spawned worker. Merely discovering a manifest never imports its Python module.
Local packages always begin disabled: a local manifest's `default_enabled = true`
cannot grant its own code permission to execute. That field is honored only for
plugins shipped inside Meshyface. Enable a new local package in the Scripts
workspace or with `--plugin-enable` when you intend to run it.

The manifest intentionally has no advisory `capabilities` field. Non-enforced
claims would add noise without changing what a trusted Python plugin can do.
The Mesh badge in the Scripts workspace is computed after the worker loads the
script and can show **Detected Write**, **Detected Read**, or **No Mesh Detected**.
If the script has not been inspected yet, the route toggle shows only **Mesh**.
Treat it as a review hint only: helper-module calls and dynamic behavior can be
missed, and broad handlers can be conservatively classified.
The route toggles remain the enforcement point for Mesh, Console, Ticker, and
View delivery.

Package directories, manifests, and files must be ordinary directories and
regular files rather than symlinks or special filesystem objects. Discovery
also rejects package paths owned by an unrelated user, world-writable paths,
and paths writable by a shared group. A user-private primary group remains
supported. Install packages read-only to other accounts and owned by root or
the dashboard service user, and keep the configured discovery root and its
parents administrator-controlled. This prevents less-privileged local writers
from changing the executable package when conventional POSIX owner and mode
bits are the access-control boundary. Remove any write-granting filesystem ACLs
from a plugin tree; extended ACL permissions are outside this check. Discovery
isolates a malformed package so other healthy packages can still run.
Manifests, command lists, package entry counts, and total package bytes have
defensive limits; rejection details appear in plugin discovery status.

Settings are optional. Supported `type` values are `text`, `boolean`, `integer`,
and `node_ids`. Text fields may declare `placeholder` and `max_length`; integer
fields may declare `minimum` and `maximum`. Every setting requires a typed
`default`. The host rejects unknown fields and invalid values before saving the
complete configuration in the plugin state database.

Dependencies are not installed automatically. Install them in the Meshyface
virtual environment, or rebuild a container image containing them. For
multi-file plugins, use package-relative imports such as
`from .helpers import build_reply`; each plugin is loaded under an isolated
package namespace in the worker.

## SDK

`meshdash.plugins` is the public namespace for the `api_version = 1` Script API:

```python
from meshdash.plugins import Script

script = Script(id="example", name="Example", version="1.0.0")


@script.command("hello")
def hello(ctx):
    ctx.peer_state["visits"] = int(ctx.peer_state.get("visits", 0)) + 1
    return ctx.reply(f"Hello, visit {ctx.peer_state['visits']}")
```

Commands use an explicit `!` prefix on the mesh, such as `!hello`. Handlers may
return one action, a list or tuple of actions, or `None`. Supported decorators
are `@script.command(...)`, `@script.on_message`, `@script.on_packet`, `@script.session`,
`@script.on_start`, and `@script.on_stop`.

The context exposes immutable normalized message information, read-only
`config`, global `state`, sender-scoped `peer_state`, session controls, logging,
and a stable service facade. Text sends, channel sends, long replies, and file sends are requests;
the host validates and schedules them after the handler completes. Node and
position lookups use a normalized snapshot, while nearest-city lookup uses the
bundled offline atlas.

`ctx.config` contains the manifest defaults merged with the administrator's
saved settings. It is a deeply read-only snapshot for the current invocation;
lists such as `node_ids` are delivered as tuples. A later invocation receives
newly saved values without a worker restart. Use `ctx.state` or
`ctx.peer_state` for Script-owned mutable data instead.

Packet handlers receive the accepted JSON-safe packet as `ctx.packet`.
This includes accepted transit traffic on monitored channels, even when the
local node is neither sender nor destination. An enabled `@script.on_packet`
plugin can therefore inspect that traffic, although it cannot suppress normal
dashboard processing. Treat packet visibility as part of the capability being
enabled.

`ctx.debug(...)` writes a bounded entry to Apps → Scripts → Script debug output
and echoes the same entry to the dashboard's foreground terminal.

Scripts may opt into display-only dashboard tickers. A Script with no ticker
declarations adds nothing to the top bar. Declared tickers exist only while its
plugin is enabled:

```python
script.ticker("activity", label="Example", default_enabled=True)


@script.on_start
def start(ctx):
    ctx.set_ticker(
        "activity",
        value="ready",
        rows={"State": "Ready", "Jobs": 0},
        state="neutral",
    )
```

`ctx.set_ticker(...)` updates host-cached UI state after a successful handler;
it never transmits over the mesh. A ticker accepts a compact scalar value, up
to eight key/value rows, a bounded detail tooltip, and a semantic `neutral`,
`good`, `warn`, or `bad` state. Declare `metric=True` and provide a finite
`metric_value` to use the standard trend display. Ticker IDs are namespaced by
Script, and disabling its plugin hides the tickers automatically.

Scripts may also declare optional node-list fields. The field definition
controls how the roster presents values. Use `default_render_kind="text"` for
plain inline writing such as `Hops 2`, or `default_render_kind="pill"` for a
framed value. The default must be one of the field's `render_kinds`.
`roster_line` controls the field's default line inside each node-list item:
line 1 is the first data line under the node name, line 2 is the next line, and
additional lines are reserved for compact plugin layouts. Existing plugins
default to line 2.

```python
script.node_field(
    "hops",
    label="Hops",
    group="Node List",
    value_type="integer",
    render_kinds=("text", "pill"),
    default_render_kind="text",
    roster_line=1,
    sortable=True,
)
```

Publish values from handlers with `ctx.set_node_field(...)`. Node IDs and field
IDs are validated by the host, and disabling the plugin removes its fields from
the roster.

State and session changes are committed only after a complete valid handler
result. Exceptions, malformed results, crashes, and timeouts send no actions and
commit no state. A timed-out invocation is dropped rather than replayed after
worker restart. Global `ctx.state` remains shared by the Script, while
`ctx.peer_state` is isolated by sender and channel. Existing databases migrate
legacy peer state to channel 0. Unchanged state is not rewritten, and empty peer
state does not create a row for a new sender. Each plugin may retain at most 512
peer-state rows, 8 MiB of aggregate peer-state JSON, and 256 active sessions.
Global and peer state intentionally survive a package update so counters and
durable workflow data continue across versions. They are not a secret store:
trusted plugin code runs as the dashboard user and can read the state database.
Active conversational sessions are cleared when the package fingerprint
changes, so an old conversation cannot silently resume in changed code.

Calling `ctx.session.start()` or `ctx.session.end()` changes the host-owned
direct-message session even when the returned session action is not included in
the handler return. Explicit commands take precedence over sessions. Public
messages never continue sessions, and direct `!quit` or `!exit` is handled by
the host even if the script worker is unavailable. Sessions are scoped by local
node, peer, and channel, so a conversation on one channel cannot resume on
another.

Enabled manifest commands are also registered as local browser Console
commands. Console execution runs through the same script worker, command
handler, peer state, and direct-message session routing used for mesh messages,
but the host captures reply actions for the browser instead of sending radio
traffic. Keep bot logic in the shared command/session handlers so a plugin can
be tested locally before using it on the mesh.

`ctx.reply_long(...)` is split on UTF-8 byte boundaries and paced by the host.
One handler result may schedule at most 64 synchronous radio frames, preventing
a large group of long replies from monopolizing the action worker. A normal
long reply remains supported. File sends and inbound file acceptance are
host-queued asynchronous jobs and do not consume this per-result
synchronous-frame allowance. Estimated outbound send airtime and the reservation
made when a plugin accepts an inbound offer count against the runtime radio
budgets. The inbound service separately applies replay limits and an ACK
cooldown plus a rolling 60-second ACK ceiling of 64 frames per sender and 128
frames globally.
`ctx.mesh.send_file(...)` queues a host-managed MF_FILE_V2 job and can only read
regular files inside the administrator-approved script files directory. File
actions also require `--file-transfer-enable` and
`--accept-file-transfer-traffic-disclaimer` (or their environment equivalents),
because they use the existing airtime-intensive file-transfer transport.

An `@script.on_packet` handler may return `ctx.accept_file()` for the direct
inbound MF_FILE_V2 metadata offer in its current packet. The host revalidates
the packet, destination, sender, channel, size limits, replay limits, and rate
limits before opening a receive session; scripts never receive the radio or
receiver service itself. There is no global auto-accept setting. Disabling a
plugin prevents it from accepting new offers, while an already accepted
transfer may finish.

Lifecycle hooks are best-effort: `on_start` can run again after a worker restart,
and `on_stop` cannot run when a hung or crashed worker must be terminated.
A plugin that hangs or fatally exits while importing is quarantined for that
package identity so it cannot periodically disrupt healthy plugins. An
unchanged identity may be retried by disabling and re-enabling it or by
restarting Meshyface. After editing the package, restart Meshyface to discover
the new fingerprint; a plugin that was already enabled resumes automatically.

## Troubleshooting

- **The Scripts workspace is missing:** remove `--no-plugins-enable`, confirm
  `MESH_DASH_PLUGINS_ENABLE` is not set to `false` or `0`, then restart
  Meshyface. This one master switch controls both workspace visibility and the
  trusted Python runtime.
- **The workspace shows zero scripts:** check the configured directory shown in
  the empty state, confirm each plugin is one direct child containing
  `plugin.toml`, and restart after copying it.
- **A plugin reports an import or definition error:** check Python syntax,
  install dependencies into the same virtual environment or container, and
  make the manifest ID, name, version, and command list exactly match the
  exported `Script`.
- **A command gets no reply:** use the `!command` spelling declared in
  `plugin.toml`, confirm the script says Running rather than Disabled or Restart
  pending, and inspect the dashboard console for timeout or handler errors.
- **A file action is rejected:** keep the file under `--plugins-files-directory`
  and enable the file-transfer feature and its traffic disclaimer.

There is no filesystem hot reload. Restart Meshyface after changing Script code,
plugin manifests, dependencies, or installation. Previously enabled plugins
resume with the changed local package, while ordinary enablement changes in the
Scripts workspace remain live.
