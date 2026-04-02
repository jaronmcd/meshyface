import types

import pytest

from meshdash import revision as revision_mod
from meshdash.revision import (
    RevisionInfo,
    coerce_revision_info,
    detect_git_commit,
    revision_info,
    sanitize_revision_token,
)


def test_sanitize_revision_token_filters_characters():
    assert sanitize_revision_token(" v1.2.3+abc!@# ", "fallback") == "v1.2.3+abc"


def test_detect_git_commit_prefers_explicit():
    commit = detect_git_commit(
        explicit_commit="abc123def",
        script_dir="/tmp",
        cwd="/tmp",
        unknown_git_commit="nogit",
    )
    assert commit == "abc123def"


def test_detect_git_commit_scans_roots_and_uses_sanitized_stdout(monkeypatch):
    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        root = cmd[2]
        if root == "/script":
            raise RuntimeError("git unavailable here")
        return types.SimpleNamespace(returncode=0, stdout=" deadbeef! \n")

    monkeypatch.setattr(revision_mod.subprocess, "run", _fake_run)
    commit = detect_git_commit(
        explicit_commit="",
        script_dir="/script",
        cwd="/cwd",
        unknown_git_commit="nogit",
    )
    assert commit == "deadbeef"
    assert calls[0][0][2] == "/script"
    assert calls[1][0][2] == "/cwd"


def test_detect_git_commit_returns_none_when_git_lookup_fails(monkeypatch):
    monkeypatch.setattr(
        revision_mod.subprocess,
        "run",
        lambda *args, **kwargs: types.SimpleNamespace(returncode=1, stdout=""),
    )
    commit = detect_git_commit(
        explicit_commit=None,
        script_dir="/same",
        cwd="/same",
        unknown_git_commit="nogit",
    )
    assert commit is None


def test_coerce_revision_info_paths():
    info = RevisionInfo(version="1", commit="a", label="L", title="T")
    assert coerce_revision_info(info) is info

    coerced = coerce_revision_info({"version": "2.0.0", "commit": "abc"})
    assert coerced.version == "2.0.0"
    assert coerced.commit == "abc"
    assert "Rev: v2.0.0" in coerced.label

    with pytest.raises(TypeError):
        coerce_revision_info(123)


def test_revision_info_uses_detect_commit_callback():
    info = revision_info(
        version_raw="v2.0.1",
        default_version="0.1.0",
        unknown_git_commit="nogit",
        detect_commit=lambda: "deadbeef",
    )
    assert isinstance(info, RevisionInfo)
    assert info.version == "2.0.1"
    assert info.commit == "deadbeef"
    assert info.label == "Rev: v2.0.1 (deadbeef)"
    assert "version 2.0.1" in info.title


def test_revision_info_fallbacks_when_detect_returns_none():
    info = revision_info(
        version_raw="",
        default_version="0.1.0",
        unknown_git_commit="nogit",
        detect_commit=lambda: None,
    )
    assert info.version == "0.1.0"
    assert info.commit == "nogit"
