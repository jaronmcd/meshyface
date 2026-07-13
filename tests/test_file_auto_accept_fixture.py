from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from meshdash.plugins import (
    AcceptFileOfferAction,
    ReplyAction,
    Script,
    SendFileAction,
)
from meshdash.plugins.manifest import parse_manifest, validate_script_against_manifest


FIXTURE = Path(__file__).parent / "fixtures" / "plugins" / "file_auto_accept"


def _load_fixture_script() -> Script:
    spec = importlib.util.spec_from_file_location(
        "meshyface_test_file_auto_accept",
        FIXTURE / "script.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert isinstance(module.script, Script)
    return module.script


def _context(*, sender_id: str, direct: bool = True, portnum: str = "258"):
    return SimpleNamespace(
        message=SimpleNamespace(
            sender_id=sender_id,
            is_direct=direct,
            portnum=portnum,
        ),
        accept_file=lambda: AcceptFileOfferAction(),
        mesh=SimpleNamespace(
            send_file=lambda destination_id, path_or_file_id: SendFileAction(
                destination_id,
                path_or_file_id,
            )
        ),
        reply=lambda text: ReplyAction(text),
    )


def test_file_auto_accept_is_a_disabled_development_fixture() -> None:
    manifest = parse_manifest(FIXTURE / "plugin.toml")
    script = _load_fixture_script()

    assert manifest.id == "file_auto_accept"
    assert manifest.commands == ("filetest",)
    assert manifest.default_enabled is False
    assert "examples" not in manifest.plugin_directory.parts
    assert validate_script_against_manifest(manifest, script) is script


def test_file_auto_accept_fixture_filters_sender_and_protocol() -> None:
    handler = _load_fixture_script().packet_handler
    assert handler is not None

    assert handler(_context(sender_id="!01020304")) == AcceptFileOfferAction()
    assert handler(_context(sender_id="!99999999")) is None
    assert handler(_context(sender_id="!01020304", direct=False)) is None
    assert handler(_context(sender_id="!01020304", portnum="POSITION_APP")) is None


def test_file_auto_accept_fixture_sends_bundled_test_file_on_direct_request() -> None:
    script = _load_fixture_script()
    handler = script.commands["filetest"]

    assert handler(_context(sender_id="!01020304")) == SendFileAction(
        "!01020304",
        "file_transfer_1k.png",
    )
    assert handler(_context(sender_id="!01020304", direct=False)) == ReplyAction(
        "Send !filetest directly to request the test file."
    )
    assert handler(_context(sender_id="!99999999")) == ReplyAction(
        "File testing is not enabled for your node."
    )
    payload = Path(__file__).parent / "fixtures" / "file_transfer_1k.png"
    assert payload.is_file()
    assert 1024 <= payload.stat().st_size < 2048
