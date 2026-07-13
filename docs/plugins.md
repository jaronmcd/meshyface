# Plugins and Script API (Alpha)

Meshyface can run administrator-installed Python plugins in a spawned worker.
Each plugin is an installed, versioned package that currently exports one
executable `Script`. The runtime is disabled by default. Its management surface is
**Apps → Scripts (Alpha)**, where an administrator can inspect installed
plugins, inspect their scripts, and save plugin enablement changes.

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

Meshyface does not pass the live radio, tracker, HTTP server, SQLite connection,
or internal locks to a script. Events, state snapshots, and requested actions
cross the worker boundary as strictly validated JSON bytes.

## Try The Hello Example With One Restart

The repository includes a copyable example at `examples/plugins/hello`. It is
documentation, not a bundled or automatically discovered plugin. Copy it into
the directory configured by `--plugins-directory`, then start or restart
Meshyface once with both the runtime and the example enabled:

```bash
mkdir -p mesh_dashboard_plugins
cp -R examples/plugins/hello mesh_dashboard_plugins/
python mesh_dashboard.py --plugins-enable --plugins-directory mesh_dashboard_plugins --plugin-enable hello
```

Keep the rest of the arguments required by your radio and HTTP setup. If a
dashboard is already running, add these options to its normal service command
and restart that service instead of launching a second dashboard. Open
**Apps → Scripts (Alpha)** and confirm that **Hello** is running, then send
`!hello` on the mesh. The reply count is stored separately for each sender.

For a container installation, place the directory under the persistent
`/data/plugins` volume and set `MESH_DASH_PLUGINS_ENABLE=1` plus
`MESH_DASH_PLUGIN_ENABLE=hello` before recreating the container. For a systemd
installation, use writable paths under `/var/lib/meshyface` rather than placing
local plugins inside the update-managed application checkout.

## Runtime Configuration

The end-to-end master switch is off by default:

```bash
python mesh_dashboard.py --plugins-enable
```

The equivalent environment setting is:

```bash
MESH_DASH_PLUGINS_ENABLE=true
```

`--no-plugins-enable` overrides an enabled environment default. When the master
switch is off, Meshyface does not discover plugins, open script state, start a
worker or dispatcher, route messages, restore sessions, or execute script
actions. Normal dashboard messaging and all non-script services remain active.

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

Individual enablement is persisted when it is changed in the Scripts workspace
and is not deleted when the master switch is off. Install, code, manifest,
dependency, and enablement changes take effect after a dashboard restart.
Runtime status appears in the normal state response under `summary.plugins`.

The alpha workspace intentionally has no code editor, package installer, or
upload surface. Administrators install and review plugin packages through the
filesystem and deployment workflow.

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
```

Manifest identity and commands are authoritative. The exported `Script` must match
them exactly. Entrypoints are confined to their plugin directory, duplicate IDs
and commands are rejected, and only enabled entrypoints are imported in the
spawned worker. Merely discovering a manifest never imports its Python module.

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

The context exposes immutable normalized message information, global `state`,
sender-scoped `peer_state`, session controls, logging, and a stable service
facade. Text sends, channel sends, long replies, and file sends are requests;
the host validates and schedules them after the handler completes. Node and
position lookups use a normalized snapshot, while nearest-city lookup uses the
bundled offline atlas.

Packet handlers receive the accepted JSON-safe packet as `ctx.packet`.
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

State and session changes are committed only after a complete valid handler
result. Exceptions, malformed results, crashes, and timeouts send no actions and
commit no state. A timed-out invocation is dropped rather than replayed after
worker restart.

Calling `ctx.session.start()` or `ctx.session.end()` changes the host-owned
direct-message session even when the returned session action is not included in
the handler return. Explicit commands take precedence over sessions. Public
messages never continue sessions, and direct `!quit` or `!exit` is handled by
the host even if the script worker is unavailable.

`ctx.reply_long(...)` is split on UTF-8 byte boundaries and paced by the host.
`ctx.mesh.send_file(...)` queues a host-managed MF_FILE_V2 job and can only read
regular files inside the administrator-approved script files directory. File
actions also require `--file-transfer-enable` and
`--accept-file-transfer-traffic-disclaimer` (or their environment equivalents),
because they use the existing airtime-intensive file-transfer transport.

Lifecycle hooks are best-effort: `on_start` can run again after a worker restart,
and `on_stop` cannot run when a hung or crashed worker must be terminated.

## Troubleshooting

- **The workspace says the master switch is off:** add `--plugins-enable` or set
  `MESH_DASH_PLUGINS_ENABLE=true`, then restart Meshyface. Installed packages are
  deliberately not inspected while the switch is off.
- **The workspace shows zero scripts:** verify `--plugins-directory`, confirm each
  plugin is one direct child containing `plugin.toml`, and restart after copying it.
  The repository `examples/` directory is never discovered automatically.
- **A plugin says Restart pending:** its desired setting was saved, but the
  running worker intentionally did not hot reload. Restart Meshyface once.
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
plugin manifests, dependencies, installation, or enablement.
