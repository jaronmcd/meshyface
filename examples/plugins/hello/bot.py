"""Minimal copyable Meshyface Scripts (Alpha) example."""

from meshdash.bots import Bot


bot = Bot(id="hello", name="Hello", version="1.0.0")


@bot.command("hello")
def hello(ctx):
    visits = int(ctx.peer_state.get("visits", 0)) + 1
    ctx.peer_state["visits"] = visits
    return ctx.reply(f"Hello from Meshyface! Visit {visits}.")
