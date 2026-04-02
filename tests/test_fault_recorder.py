from meshdash.fault_recorder import FaultRecorder


def test_fault_recorder_records_defaults_and_recent_ordering():
    seq = {"now": 1710001000}

    def _now():
        return float(seq["now"])

    recorder = FaultRecorder(now_unix_fn=_now, max_rows=10)
    first = recorder.record_fault({"source": "bot", "code": "ONE", "message": "first"})
    seq["now"] = 1710001010
    second = recorder.record_fault({"source": "radio", "code": "TWO", "message": "second"})

    assert first["code"] == "ONE"
    assert second["code"] == "TWO"
    rows = recorder.recent_faults()
    assert len(rows) == 2
    assert rows[0]["id"] == second["id"]
    assert rows[1]["id"] == first["id"]


def test_fault_recorder_supports_source_filter():
    recorder = FaultRecorder(now_unix_fn=lambda: 1710001000.0, max_rows=10)
    recorder.record_fault({"source": "bot", "code": "BOT_FAULT"})
    recorder.record_fault({"source": "radio", "code": "RF_FAULT"})

    bot_rows = recorder.recent_faults(source="bot")
    assert len(bot_rows) == 1
    assert bot_rows[0]["code"] == "BOT_FAULT"


def test_fault_recorder_trims_to_max_rows():
    now = {"unix": 1710001000}

    def _now():
        return float(now["unix"])

    recorder = FaultRecorder(now_unix_fn=_now, max_rows=2)
    recorder.record_fault({"source": "bot", "code": "A"})
    now["unix"] += 1
    recorder.record_fault({"source": "bot", "code": "B"})
    now["unix"] += 1
    recorder.record_fault({"source": "bot", "code": "C"})

    rows = recorder.recent_faults()
    assert len(rows) == 2
    codes = [str(row.get("code")) for row in rows]
    assert codes == ["C", "B"]
