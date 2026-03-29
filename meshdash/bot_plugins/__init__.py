"""Optional non-core bot apps.

Drop plugin modules in this package and export either:
- build_bot_apps() -> iterable of BotApp instances, or
- BOT_APPS = [...]

Notes:
- Underscore-prefixed modules are treated as templates/private helpers and are
  skipped by auto-discovery.
- For easier command bots, use the SDK in ``meshdash.bot_sdk``.
"""
