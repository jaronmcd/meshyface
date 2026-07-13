# Scripts (Alpha)

Meshyface can run administrator-installed Python automations in a spawned
worker. The feature is disabled by default. Its management surface is
**Apps → Scripts (Alpha)**, where an administrator can inspect installed
scripts and save enablement changes.

The word **Alpha** describes this management UI. Script packages use the
versioned `api_version = 1` host/worker protocol. For compatibility, the first
protocol keeps the existing `meshdash.bots` SDK import, `--bots-*` command-line
options, and `MESH_DASH_BOTS_*` environment settings. The singular
`--bot-enable` / `--bot-disable` options and `MESH_DASH_BOT_ENABLE` /
`MESH_DASH_BOT_DISABLE` settings select individual script IDs. These names are
intentional compatibility interfaces even though the product UI calls the
feature Scripts.

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
documentation, not a bundled or automatically discovered script. Copy it into
the directory configured by `--bots-directory`, then start or restart
Meshyface once with both the runtime and the example enabled:

```bash
mkdir -p mesh_dashboard_plugins
cp -R examples/plugins/hello mesh_dashboard_plugins/
python mesh_dashboard.py \
  --bots-enable \
  --bots-directory mesh_dashboard_plugins \
  --bot-enable hello
```

Keep the rest of the arguments required by your radio and HTTP setup. If a
dashboard is already running, add these options to its normal service command
and restart that service instead of launching a second dashboard. Open
**Apps → Scripts (Alpha)** and confirm that **Hello** is running, then send
`!hello` on the mesh. The reply count is stored separately for each sender.

For a container installation, place the directory under the persistent
`/data/plugins` volume and set `MESH_DASH_BOTS_ENABLE=1` plus
`MESH_DASH_BOT_ENABLE=hello` before recreating the container. For a systemd
installation, use writable paths under `/var/lib/meshyface` rather than placing
local scripts inside the update-managed application checkout.

## Runtime Configuration

The end-to-end master switch is off by default:

```bash
python mesh_dashboard.py --bots-enable
```

The equivalent environment setting is:

```bash
MESH_DASH_BOTS_ENABLE=true
```

`--no-bots-enable` overrides an enabled environment default. When the master
switch is off, Meshyface does not discover scripts, open script state, start a
worker or dispatcher, route messages, restore sessions, or execute script
actions. Normal dashboard messaging and all non-script services remain active.

Relevant startup options are:

- `--bots-directory PATH`: persistent local script package directory.
- `--bots-state-db PATH`: independent state, session, and enablement database.
- `--bots-files-directory PATH`: approved root for script-requested file sends.
- `--bots-handler-timeout SECONDS`: handler deadline before worker restart.
- `--bots-event-queue-size COUNT`: bounded pending-event capacity.
- `--bot-enable ID` and `--bot-disable ID`: repeatable per-script overrides.

The path options also accept `MESH_DASH_BOTS_DIRECTORY`,
`MESH_DASH_BOTS_STATE_DB`, and `MESH_DASH_BOTS_FILES_DIRECTORY`. Initial
per-script overrides may be supplied as comma-separated
`MESH_DASH_BOT_ENABLE` and `MESH_DASH_BOT_DISABLE` values.

Individual enablement is persisted when it is changed in the Scripts workspace
and is not deleted when the master switch is off. Install, code, manifest,
dependency, and enablement changes take effect after a dashboard restart.
Runtime status appears in the normal state response under `summary.plugins`.

The alpha workspace intentionally has no code editor, package installer, or
upload surface. Administrators install and review script packages through the
filesystem and deployment workflow.

## Script Package

Each script is one direct child directory containing a manifest and entrypoint:

```text
my_script/
    bot.toml
    bot.py
```

Example `bot.toml`:

```toml
api_version = 1
id = "example"
name = "Example"
version = "1.0.0"
entrypoint = "bot.py:bot"
commands = ["hello"]
default_enabled = false
```

Manifest identity and commands are authoritative. The exported `Bot` must match
them exactly. Entrypoints are confined to their script directory, duplicate IDs
and commands are rejected, and only enabled entrypoints are imported in the
spawned worker. Merely discovering a manifest never imports its Python module.

Dependencies are not installed automatically. Install them in the Meshyface
virtual environment, or rebuild a container image containing them. For
multi-file scripts, use package-relative imports such as
`from .helpers import build_reply`; each script is loaded under an isolated
package namespace in the worker.

## SDK

`meshdash.bots` is the compatibility namespace for the `api_version = 1` SDK:

```python
from meshdash.bots import Bot

bot = Bot(id="example", name="Example", version="1.0.0")


@bot.command("hello")
def hello(ctx):
    ctx.peer_state["visits"] = int(ctx.peer_state.get("visits", 0)) + 1
    return ctx.reply(f"Hello, visit {ctx.peer_state['visits']}")
```

Commands use an explicit `!` prefix on the mesh, such as `!hello`. Handlers may
return one action, a list or tuple of actions, or `None`. Supported decorators
are `@bot.command(...)`, `@bot.on_message`, `@bot.on_packet`, `@bot.session`,
`@bot.on_start`, and `@bot.on_stop`.

The context exposes immutable normalized message information, global `state`,
sender-scoped `peer_state`, session controls, logging, and a stable service
facade. Text sends, channel sends, long replies, and file sends are requests;
the host validates and schedules them after the handler completes. Node and
position lookups use a normalized snapshot, while nearest-city lookup uses the
bundled offline atlas.

Packet handlers receive the accepted JSON-safe packet as `ctx.packet`.
`ctx.debug(...)` writes a bounded entry to Apps → Scripts → Script debug output
and echoes the same entry to the dashboard's foreground terminal.

Scripts may opt into display-only dashboard tickers. A script with no ticker
declarations adds nothing to the top bar. Declared tickers exist only while the
script is enabled:

```python
bot.ticker("activity", label="Example", default_enabled=True)


@bot.on_start
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
script, and disabling the script hides its tickers automatically.

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

- **The workspace says the master switch is off:** add `--bots-enable` or set
  `MESH_DASH_BOTS_ENABLE=true`, then restart Meshyface. Installed packages are
  deliberately not inspected while the switch is off.
- **The workspace shows zero scripts:** verify `--bots-directory`, confirm each
  script is one direct child containing `bot.toml`, and restart after copying it.
  The repository `examples/` directory is never discovered automatically.
- **A script says Restart pending:** its desired setting was saved, but the
  running worker intentionally did not hot reload. Restart Meshyface once.
- **A script reports an import or definition error:** check Python syntax,
  install dependencies into the same virtual environment or container, and
  make the manifest ID, name, version, and command list exactly match the
  exported `Bot`.
- **A command gets no reply:** use the `!command` spelling declared in
  `bot.toml`, confirm the script says Running rather than Disabled or Restart
  pending, and inspect the dashboard console for timeout or handler errors.
- **A file action is rejected:** keep the file under `--bots-files-directory`
  and enable the file-transfer feature and its traffic disclaimer.

There is no filesystem hot reload. Restart Meshyface after changing script code,
manifests, dependencies, installation, or enablement.
