from meshdash.plugins import Script


script = Script(
    id="file_auto_accept",
    name="File Auto Accept Test",
    version="1.0.0",
)

# Development fixture only. Replace these canonical IDs for a local test.
ALLOWED_SENDER_IDS = frozenset({"!01020304"})
TEST_FILE_NAME = "file_transfer_1k.png"


@script.command("filetest")
def send_test_file(ctx):
    if not ctx.message.is_direct:
        return ctx.reply("Send !filetest directly to request the test file.")
    if ctx.message.sender_id not in ALLOWED_SENDER_IDS:
        return ctx.reply("File testing is not enabled for your node.")
    return ctx.mesh.send_file(ctx.message.sender_id, TEST_FILE_NAME)


@script.on_packet
def accept_allowed_file_offer(ctx):
    if not ctx.message.is_direct or ctx.message.portnum != "258":
        return None
    if ctx.message.sender_id not in ALLOWED_SENDER_IDS:
        return None
    return ctx.accept_file()
