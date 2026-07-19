import importlib.util
import json
from pathlib import Path


def _load_diag_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "longterm_dashboard_diagnostic.py"
    spec = importlib.util.spec_from_file_location("longterm_dashboard_diagnostic", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_append_cachebuster_preserves_existing_query() -> None:
    diag = _load_diag_module()

    assert (
        diag.append_cachebuster("http://127.0.0.1:8877/api/state?lite=1&profile=chat", "abc")
        == "http://127.0.0.1:8877/api/state?lite=1&profile=chat&_mesh_diag=abc"
    )


def test_endpoint_url_joins_base_url_and_endpoint() -> None:
    diag = _load_diag_module()

    assert (
        diag.endpoint_url("http://192.168.1.87:8877", "/api/state?lite=1")
        == "http://192.168.1.87:8877/api/state?lite=1"
    )
    assert (
        diag.endpoint_url("http://192.168.1.87:8877/base", "api/version")
        == "http://192.168.1.87:8877/api/version"
    )
    assert (
        diag.endpoint_url("http://127.0.0.1:8877", "http://example.test/api/state")
        == "http://example.test/api/state"
    )


def test_parse_proc_status_converts_kb_and_integer_fields() -> None:
    diag = _load_diag_module()

    parsed = diag.parse_proc_status(
        "\n".join(
            [
                "Name:\tpython",
                "VmRSS:\t  123456 kB",
                "VmSize:\t  789000 kB",
                "Threads:\t7",
            ]
        )
    )

    assert parsed["Name"] == "python"
    assert parsed["VmRSS_kb"] == 123456
    assert parsed["VmSize_kb"] == 789000
    assert parsed["Threads"] == 7


def test_system_metrics_parses_meminfo(monkeypatch) -> None:
    diag = _load_diag_module()

    def fake_read_text(path: Path) -> str | None:
        if str(path) == "/proc/meminfo":
            return "MemTotal:        2024304 kB\nMemAvailable:    1500000 kB\n"
        if str(path) == "/proc/loadavg":
            return "0.00 0.01 0.00 1/101 12345\n"
        return None

    monkeypatch.setattr(diag, "read_text", fake_read_text)

    metrics = diag.system_metrics()

    assert metrics["loadavg"] == "0.00 0.01 0.00 1/101 12345"
    assert metrics["meminfo"]["MemTotal_kb"] == 2024304
    assert metrics["meminfo"]["MemAvailable_kb"] == 1500000


def test_file_family_sizes_reports_db_wal_and_shm(tmp_path: Path) -> None:
    diag = _load_diag_module()
    db_path = tmp_path / "history.sqlite3"
    wal_path = tmp_path / "history.sqlite3-wal"
    db_path.write_bytes(b"db")
    wal_path.write_bytes(b"wal")

    sizes = diag.file_family_sizes(str(db_path))

    assert sizes["path"] == str(db_path)
    assert sizes["db_bytes"] == 2
    assert sizes["wal_bytes"] == 3
    assert sizes["shm_bytes"] is None


def test_write_sample_appends_jsonl(tmp_path: Path) -> None:
    diag = _load_diag_module()
    output = tmp_path / "diag" / "samples.jsonl"

    diag.write_sample(output, {"sample_index": 0, "ok": True})
    diag.write_sample(output, {"sample_index": 1, "ok": False})

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"ok": True, "sample_index": 0}, {"ok": False, "sample_index": 1}]
