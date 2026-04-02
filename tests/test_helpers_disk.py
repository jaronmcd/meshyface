from collections import namedtuple

from meshdash import helpers_disk


DiskUsage = namedtuple("usage", ["total", "used", "free"])


def test_disk_space_info_for_file_path_and_success(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text("x")

    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", lambda _probe: DiskUsage(1000, 250, 750))
    monkeypatch.setattr(helpers_disk, "_DISK_CACHE", {"probe": None, "ts": 0.0, "payload": None})

    info = helpers_disk.disk_space_info(str(file_path))
    assert info["path"] == str(tmp_path)
    assert info["total_bytes"] == 1000
    assert info["used_bytes"] == 250
    assert info["free_bytes"] == 750
    assert info["free_pct"] == 75.0
    assert info["used_pct"] == 25.0


def test_disk_space_info_returns_cached_payload(monkeypatch):
    probe = "/tmp"
    monkeypatch.setattr(helpers_disk.os.path, "abspath", lambda p: probe)
    monkeypatch.setattr(helpers_disk.os.path, "expanduser", lambda p: p)
    monkeypatch.setattr(helpers_disk.os.path, "isfile", lambda _p: False)
    monkeypatch.setattr(helpers_disk.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        helpers_disk,
        "_DISK_CACHE",
        {"probe": probe, "ts": 90.5, "payload": {"path": probe, "free_bytes": 10}},
    )

    info = helpers_disk.disk_space_info(probe)
    assert info == {"path": probe, "free_bytes": 10}
    assert info is not helpers_disk._DISK_CACHE["payload"]


def test_disk_space_info_error_path_caches_error_payload(monkeypatch):
    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", lambda _probe: (_ for _ in ()).throw(OSError("no disk")))
    monkeypatch.setattr(helpers_disk, "_DISK_CACHE", {"probe": None, "ts": 0.0, "payload": None})
    monkeypatch.setattr(helpers_disk.time, "time", lambda: 222.0)

    info = helpers_disk.disk_space_info(".")
    assert "error" in info
    assert "no disk" in info["error"]
    assert helpers_disk._DISK_CACHE["payload"]["error"] == info["error"]


def test_disk_space_info_ignores_cache_write_failures(monkeypatch):
    class _BrokenCache(dict):
        def __setitem__(self, _key, _value):
            raise RuntimeError("cache write failed")

    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", lambda _probe: DiskUsage(10, 2, 8))
    monkeypatch.setattr(helpers_disk, "_DISK_CACHE", _BrokenCache())

    info = helpers_disk.disk_space_info(".")
    assert info["total_bytes"] == 10
    assert info["free_bytes"] == 8
