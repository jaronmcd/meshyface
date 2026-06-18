from types import SimpleNamespace

import meshdash.helpers_disk as helpers_disk
import meshdash.helpers_emoji as helpers_emoji
import meshdash.revision as revision
from meshdash.helpers_disk import disk_space_info
from meshdash.helpers_emoji import emoji_codepoint_from_any, emoji_from_codepoint, normalize_single_emoji
from meshdash.revision import (
    RevisionInfo,
    coerce_revision_info,
    detect_git_commit,
    revision_info,
    sanitize_revision_token,
)
from meshdash.runtime_lifecycle import (
    close_runtime_resources,
    emit_startup_status,
    guess_lan_ipv4,
    serve_until_stopped,
)


def test_revision_info_coercion_sanitizing_and_detection(monkeypatch) -> None:
    info = RevisionInfo(version="1.2.3", commit="abc", label="label", title="title")
    assert coerce_revision_info(info) is info
    assert info.as_dict() == {"version": "1.2.3", "commit": "abc", "label": "label", "title": "title"}
    assert coerce_revision_info({"version": "2", "commit": "def"}).label == "Rev: v2 (def)"
    assert sanitize_revision_token("", "fallback") == "fallback"
    assert sanitize_revision_token(" bad token!* ", "fallback") == "badtoken"
    assert sanitize_revision_token(" !!! ", "fallback") == "fallback"
    assert detect_git_commit(" explicit! ", "/repo", "/repo", "nogit") == "explicit"

    calls: list[str] = []

    def _run(cmd, **kwargs):
        calls.append(cmd[2])
        if len(calls) == 1:
            raise OSError("git unavailable")
        return SimpleNamespace(returncode=0, stdout=" abc123dirty \n")

    monkeypatch.setattr(revision.subprocess, "run", _run)

    assert detect_git_commit("", "/repo1", "/repo2", "nogit") == "abc123dirty"
    assert calls == ["/repo1", "/repo2"]

    monkeypatch.setattr(
        revision.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert detect_git_commit("", "/repo", "/repo", "nogit") is None

    built = revision_info("v3.0", "0.0.0", "nogit", detect_commit=lambda: "abc123")
    assert built.version == "3.0"
    assert built.label == "Rev: v3.0 (abc123)"
    try:
        coerce_revision_info("bad")  # type: ignore[arg-type]
    except TypeError as exc:
        assert "Expected RevisionInfo or mapping" in str(exc)
    else:
        raise AssertionError("coerce_revision_info should reject non-mapping values")


def test_guess_lan_ipv4_uses_udp_then_hostname_fallback() -> None:
    class Socket:
        def __init__(self, *, fail_connect: bool = False, ip: str = "192.168.1.10") -> None:
            self.fail_connect = fail_connect
            self.ip = ip

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def connect(self, address):
            if self.fail_connect:
                raise OSError("offline")

        def getsockname(self):
            return (self.ip, 12345)

    class PrimarySocketModule:
        AF_INET = 2
        SOCK_DGRAM = 2
        gaierror = OSError

        def socket(self, family, socktype):
            return Socket(ip="192.168.1.10")

        def gethostname(self):
            return "host"

        def getaddrinfo(self, hostname, service, *, family=None):
            return []

    class FallbackSocketModule(PrimarySocketModule):
        def socket(self, family, socktype):
            return Socket(fail_connect=True)

        def getaddrinfo(self, hostname, service, *, family=None):
            return [
                (family, 0, 0, "", ("127.0.0.1", 0)),
                (family, 0, 0, "", ("10.0.0.5", 0)),
            ]

    class MissingSocketModule(FallbackSocketModule):
        def getaddrinfo(self, hostname, service, *, family=None):
            raise self.gaierror("missing")

    assert guess_lan_ipv4(PrimarySocketModule()) == "192.168.1.10"
    assert guess_lan_ipv4(FallbackSocketModule()) == "10.0.0.5"
    assert guess_lan_ipv4(MissingSocketModule()) is None


def test_emit_startup_status_serve_and_close_runtime_resources() -> None:
    lines: list[str] = []
    emit_startup_status(
        http_host="0.0.0.0",
        bound_host="0.0.0.0",
        bound_port=8877,
        show_secrets=False,
        revision_info=RevisionInfo(version="1", commit="abc", label="", title=""),
        history_enabled=True,
        history_db_path="/tmp/history.sqlite3",
        history_retention_days=30,
        history_max_rows=200,
        history_event_retention_days=7,
        history_event_max_rows=100,
        history_rollup_retention_days=365,
        guess_lan_ipv4_fn=lambda: "10.0.0.5",
        out_fn=lines.append,
    )
    emit_startup_status(
        http_host="127.0.0.1",
        bound_host="127.0.0.1",
        bound_port=8878,
        show_secrets=True,
        revision_info=RevisionInfo(version="1", commit="abc", label="", title=""),
        history_enabled=False,
        history_db_path="",
        history_retention_days=0,
        history_max_rows=0,
        history_event_retention_days=0,
        history_event_max_rows=0,
        history_rollup_retention_days=0,
        guess_lan_ipv4_fn=lambda: None,
        out_fn=lines.append,
    )
    emit_startup_status(
        http_host="::",
        bound_host="::",
        bound_port=8879,
        show_secrets=True,
        revision_info=RevisionInfo(version="1", commit="abc", label="", title=""),
        history_enabled=False,
        history_db_path="",
        history_retention_days=0,
        history_max_rows=0,
        history_event_retention_days=0,
        history_event_max_rows=0,
        history_rollup_retention_days=0,
        guess_lan_ipv4_fn=lambda: None,
        out_fn=lines.append,
    )

    assert "Open from Wi-Fi devices: http://10.0.0.5:8877" in lines
    assert "Secrets are redacted. Use --show-secrets to display full values." in lines
    assert any(line.startswith("History DB: /tmp/history.sqlite3") for line in lines)
    assert "Open: http://127.0.0.1:8878" in lines
    assert "Open from Wi-Fi devices: http://<this-computer-ip>:8879" in lines
    assert "History DB: disabled" in lines

    server = SimpleNamespace(
        serve_forever=lambda poll_interval: (_ for _ in ()).throw(KeyboardInterrupt()),
        server_close=lambda: (_ for _ in ()).throw(RuntimeError("close failed")),
    )
    iface = SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("close failed")))
    history_store = SimpleNamespace(close=lambda: (_ for _ in ()).throw(RuntimeError("close failed")))
    stopped: list[str] = []

    serve_until_stopped(server, poll_interval=0.01, out_fn=stopped.append)
    close_runtime_resources(server=server, iface=iface, history_store=history_store)
    close_runtime_resources(server=server, iface=iface, history_store=None)

    assert stopped == ["Stopping dashboard..."]


def test_disk_space_info_reports_usage_caches_and_errors(monkeypatch) -> None:
    helpers_disk._DISK_CACHE.update({"probe": None, "ts": 0.0, "payload": None})
    usage_calls: list[str] = []

    monkeypatch.setattr(helpers_disk.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(helpers_disk.os.path, "dirname", lambda path: "/base")
    monkeypatch.setattr(helpers_disk.time, "time", lambda: 100.0)

    def _disk_usage(path: str):
        usage_calls.append(path)
        return SimpleNamespace(total=100, used=25, free=75)

    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", _disk_usage)

    first = disk_space_info("/tmp/file")
    second = disk_space_info("/tmp/file")

    assert first["path"] == "/base"
    assert first["free_pct"] == 75.0
    assert second == first
    assert usage_calls == ["/base"]

    helpers_disk._DISK_CACHE.update({"probe": None, "ts": 0.0, "payload": None})
    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", lambda path: (_ for _ in ()).throw(OSError("no disk")))
    error = disk_space_info("/tmp/file")
    assert error["path"] == "/base"
    assert error["error"] == "no disk"

    class BrokenCache(dict):
        def get(self, *args, **kwargs):
            raise RuntimeError("cache read failed")

        def __setitem__(self, key, value):
            raise RuntimeError("cache write failed")

    monkeypatch.setattr(helpers_disk, "_DISK_CACHE", BrokenCache())
    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", _disk_usage)
    assert disk_space_info("/tmp/file")["free_pct"] == 75.0
    monkeypatch.setattr(helpers_disk.shutil, "disk_usage", lambda path: (_ for _ in ()).throw(OSError("no disk")))
    assert disk_space_info("/tmp/file")["error"] == "no disk"


def test_emoji_helpers_normalize_single_reaction_codepoints() -> None:
    smile = chr(0x1F642)
    with_variation = chr(0xFE0F) + smile

    assert emoji_from_codepoint(None) is None
    assert emoji_from_codepoint(65) is None
    assert emoji_from_codepoint(0x110000) is None
    assert emoji_from_codepoint(0x1F642) == smile
    assert emoji_codepoint_from_any(None) is None
    assert emoji_codepoint_from_any("") is None
    assert emoji_codepoint_from_any("65") is None
    assert emoji_codepoint_from_any("U+1F642") == 0x1F642
    assert emoji_codepoint_from_any(smile) == 0x1F642
    assert emoji_codepoint_from_any(with_variation) == 0x1F642
    assert emoji_codepoint_from_any(smile + smile) is None
    assert emoji_codepoint_from_any(0x1F642) == 0x1F642
    assert emoji_codepoint_from_any(object()) is None
    assert normalize_single_emoji(smile) == (smile, 0x1F642)
    assert normalize_single_emoji("x") == (None, None)


def test_normalize_single_emoji_handles_failed_codepoint_conversion(monkeypatch) -> None:
    monkeypatch.setattr(helpers_emoji, "emoji_from_codepoint", lambda codepoint: None)

    assert normalize_single_emoji(0x1F642) == (None, None)
