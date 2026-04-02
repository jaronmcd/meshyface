from meshdash.bot_apps.base import BotAppResult
from meshdash.bot_commands import BotCommandSpec
from meshdash.bot_sdk import CommandApp, CommandInvocation


def test_command_app_handles_matching_head_and_returns_text():
    app = CommandApp(
        spec=BotCommandSpec(
            name="echo",
            usage="echo <text>",
            description="repeat text",
        ),
        handler=lambda invocation: f"echo: {' '.join(invocation.args)}",
    )

    result = app.try_handle_message(
        text="echo hello mesh",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    assert result.handled is True
    assert result.reply_text == "echo: hello mesh"
    assert result.command_name == "echo"
    assert result.command_args == ("hello", "mesh")


def test_command_app_supports_prefix_and_alias_matching():
    app = CommandApp(
        spec=BotCommandSpec(
            name="echo",
            usage="echo <text>",
            description="repeat text",
        ),
        handler=lambda invocation: f"echo: {' '.join(invocation.args)}",
        aliases=("say",),
    )

    slash = app.try_handle_message(
        text="/echo hi",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    alias = app.try_handle_message(
        text="say hello",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    assert slash.handled is True
    assert alias.handled is True
    assert slash.command_name == "echo"
    assert alias.command_name == "echo"


def test_command_app_returns_handled_without_reply_when_disabled():
    app = CommandApp(
        spec=BotCommandSpec(
            name="echo",
            usage="echo <text>",
            description="repeat text",
        ),
        handler=lambda _invocation: "this should not be used while disabled",
    )

    result = app.try_handle_message(
        text="echo hello",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=False,
    )
    assert result.handled is True
    assert result.reply_text is None
    assert result.command_name == "echo"


def test_command_app_can_require_direct_messages_to_local_node():
    app = CommandApp(
        spec=BotCommandSpec(
            name="secure",
            usage="secure",
            description="direct-only command",
        ),
        handler=lambda _invocation: "ok",
        require_direct_to_local=True,
    )

    broadcast = app.try_handle_message(
        text="secure",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    direct = app.try_handle_message(
        text="secure",
        from_id="!abcd1234",
        to_id="!02ed9b7c",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    assert broadcast.handled is False
    assert direct.handled is True
    assert direct.reply_text == "ok"


def test_command_app_accepts_bot_app_result_from_handler():
    def _handler(invocation: CommandInvocation) -> BotAppResult:
        return BotAppResult(
            handled=True,
            reply_text=f"pong {' '.join(invocation.args)}",
            command_name="",
        )

    app = CommandApp(
        spec=BotCommandSpec(
            name="pingx",
            usage="pingx <text>",
            description="returns BotAppResult",
        ),
        handler=_handler,
    )

    result = app.try_handle_message(
        text="pingx one two",
        from_id="!abcd1234",
        to_id="^all",
        local_node_id="!02ed9b7c",
        now_unix=1710000000,
        enabled=True,
    )
    assert result.handled is True
    assert result.command_name == "pingx"
    assert result.reply_text == "pong one two"
