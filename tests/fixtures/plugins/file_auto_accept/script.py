from meshdash.plugins import Script


script = Script(
    id="file_auto_accept",
    name="File Auto Accept Test",
    version="1.0.0",
)

TEST_FILE_NAME = "file_transfer_1k.png"


def _sender_is_allowed(ctx):
    return ctx.message.sender_id in ctx.config["allowed_sender_ids"]


@script.command("filetest")
def send_test_file(ctx):
    if not ctx.message.is_direct:
        return ctx.reply("Send !filetest directly to request the test file.")
    if not _sender_is_allowed(ctx):
        return ctx.reply("File testing is not enabled for your node.")
    return ctx.mesh.send_file(ctx.message.sender_id, TEST_FILE_NAME)


@script.on_packet
def accept_allowed_file_offer(ctx):
    if not ctx.message.is_direct or ctx.message.portnum != "258":
        return None
    if not _sender_is_allowed(ctx):
        return None
    return ctx.accept_file()
