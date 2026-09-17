def test_scheduled_polls_back_off_after_slow_polls_instead_of_queueing(dashboard_js: str) -> None:
    # Guard: with setInterval + queue-on-busy, a poll slower than the refresh interval made the
    # next poll start immediately, so slow devices polled nonstop (98% main-thread busy in a
    # 20x CPU benchmark). Scheduled ticks must skip while a poll runs and wait for idle time.
    assert "async function pollOnce(options = null) {" in dashboard_js
    assert "if (!scheduled) pollQueued = true;" in dashboard_js
    assert "const idleNeededMs = Math.min(refreshMs, lastPollDurationMs);" in dashboard_js
    assert "if (scheduledPollShouldWait(nowMs)) {" in dashboard_js
    assert "void pollOnce({ scheduled: true });" in dashboard_js


def test_polls_pause_while_typing_and_catch_up_after(dashboard_js: str) -> None:
    # Guard: typing used to fetch and parse full state about every second only to defer the
    # render. Neither the scheduler nor the immediate-poll timer may fetch while typing.
    assert "const typingRemainingMs = dashboardTextEntryRenderDeferRemainingMs();" in dashboard_js
    assert "requestImmediatePoll(Math.ceil(typingRemainingMs) + 80);" in dashboard_js
    assert "if (typingRemainingMs > 0 && latestState) {" in dashboard_js
