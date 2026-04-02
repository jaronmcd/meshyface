from dataclasses import dataclass


@dataclass(frozen=True)
class BotCommandSpec:
    name: str
    usage: str
    description: str
    kind: str = "builtin"


DEFAULT_ENABLED_MANAGED_BOT_COMMAND_NAMES = (
    "ping",
    "joke",
    "pull",
    "zork",
)


def normalize_bot_command_name(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if text.startswith("!") or text.startswith("#"):
        text = text[1:]
    if not text:
        return ""
    out = []
    for ch in text:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch in ("_", "-"):
            out.append(ch)
    return "".join(out)


MANAGED_BOT_COMMAND_SPECS = (
    BotCommandSpec(
        name="ping",
        usage="ping [target]",
        description="measure reply latency and hop path",
    ),
    BotCommandSpec(
        name="joke",
        usage="joke",
        description="tell a random joke",
    ),
    BotCommandSpec(
        name="pull",
        usage="/pull",
        description="spin a 3-reel slot machine",
    ),
    BotCommandSpec(
        name="zork",
        usage="zork",
        description="start the peer-to-peer text adventure",
        kind="game",
    ),
    BotCommandSpec(
        name="cmd",
        usage="cmd",
        description="show available bot commands",
    ),
    BotCommandSpec(
        name="help",
        usage="help",
        description="basic usage/help menu",
    ),
    BotCommandSpec(
        name="whoami",
        usage="whoami",
        description="show your local node identity",
    ),
    BotCommandSpec(
        name="whois",
        usage="whois <id>",
        description="lookup node by id or suffix",
    ),
    BotCommandSpec(
        name="whohas",
        usage="whohas <name>",
        description="lookup node by name",
    ),
    BotCommandSpec(
        name="lheard",
        usage="lheard",
        description="list recently heard nodes",
    ),
)

MANAGED_BOT_COMMAND_SPECS_BY_NAME = {
    spec.name: spec for spec in MANAGED_BOT_COMMAND_SPECS
}

STANDARD_BOT_COMMANDS = tuple(
    spec.name for spec in MANAGED_BOT_COMMAND_SPECS if spec.kind == "builtin"
)


def build_custom_bot_command_spec(name: object) -> BotCommandSpec:
    clean = normalize_bot_command_name(name)
    return BotCommandSpec(
        name=clean,
        usage=clean,
        description="custom command template",
        kind="custom",
    )


__all__ = [
    "DEFAULT_ENABLED_MANAGED_BOT_COMMAND_NAMES",
    "BotCommandSpec",
    "MANAGED_BOT_COMMAND_SPECS",
    "MANAGED_BOT_COMMAND_SPECS_BY_NAME",
    "STANDARD_BOT_COMMANDS",
    "build_custom_bot_command_spec",
    "normalize_bot_command_name",
]
