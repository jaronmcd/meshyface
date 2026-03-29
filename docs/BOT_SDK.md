# Bot SDK Guide

Doc status: active-runtime
Last reviewed: 2026-03-29

This project supports external bot plugins, and now includes a small SDK to
make plugin authoring easier.

## Goal

- Keep core app logic stable.
- Let contributors add bots from separate modules/folders.
- Reduce boilerplate for common "single command" bots.

## Fast Start

1. Copy `meshdash/bot_plugins/_sdk_template.py` to a new file without the
   leading underscore.
2. Edit the command name/usage/description and handler logic.
3. Restart the app. Modules under `meshdash.bot_plugins.*` auto-load.

## SDK Surface

- `meshdash.bot_sdk.CommandApp`
- `meshdash.bot_sdk.CommandInvocation`

`CommandApp` wraps a simple callback and handles:

- command head parsing (`echo`, `/echo`, `!echo`, `#echo`)
- optional aliases
- optional direct-only gating (`require_direct_to_local=True`)
- disabled-command behavior (`handled=True`, no reply)

## Plugin Loader Notes

- Underscore-prefixed plugin modules are skipped by auto-discovery.
- You can still load explicit external modules via:
  - `MESH_DASH_BOT_PLUGIN_MODULES`
  - `MESH_DASH_BOT_PLUGIN_STRICT=1` (fail fast on bad modules)
