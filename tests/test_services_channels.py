import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash.api_input_channels import ChannelSettingsRequest
from meshdash.services_channels import apply_channel_settings


class _FakeRole:
    DISABLED = 0
    PRIMARY = 1
    SECONDARY = 2

    @staticmethod
    def Name(value: int) -> str:
        return {
            0: "DISABLED",
            1: "PRIMARY",
            2: "SECONDARY",
        }.get(int(value), str(value))


class _FakeChannelClass:
    Role = _FakeRole


class _FakeChannelPb2:
    Channel = _FakeChannelClass


class _FakeSettings:
    def __init__(self, *, name: str = "", psk: object = None, uplink_enabled: bool = False, downlink_enabled: bool = False):
        self.name = name
        self.psk = psk
        self.uplink_enabled = uplink_enabled
        self.downlink_enabled = downlink_enabled


class _FakeModuleSettings:
    def __init__(self) -> None:
        self.is_muted = False
        self.position_precision = 0


class _FakeChannel:
    def __init__(self, *, index: int, role: int, name: str = "", psk: object = None) -> None:
        self.index = index
        self.role = role
        self.settings = _FakeSettings(name=name, psk=psk)
        self.module_settings = _FakeModuleSettings()


def _clone_channels(channels: list[_FakeChannel]) -> list[_FakeChannel]:
    return deepcopy(channels)


class _FakeNode:
    def __init__(self) -> None:
        self._live_channels = [
            _FakeChannel(index=0, role=_FakeRole.PRIMARY, psk=b"default"),
            _FakeChannel(index=1, role=_FakeRole.SECONDARY, name="test", psk=b"default"),
            _FakeChannel(index=2, role=_FakeRole.DISABLED),
            _FakeChannel(index=3, role=_FakeRole.DISABLED),
        ]
        self.channels = _clone_channels(self._live_channels)
        self.transaction_open = False
        self.write_calls: list[int] = []
        self.delete_calls: list[int] = []

    def requestChannels(self, startingIndex: int = 0) -> None:  # noqa: N802
        if startingIndex == 0:
            self.channels = _clone_channels(self._live_channels)

    def waitForConfig(self, _name: str) -> None:  # noqa: N802
        return None

    def beginSettingsTransaction(self) -> None:  # noqa: N802
        self.transaction_open = True

    def commitSettingsTransaction(self) -> None:  # noqa: N802
        if self.transaction_open:
            self._live_channels = _clone_channels(self.channels)
        self.transaction_open = False

    def writeChannel(self, index: int) -> None:  # noqa: N802
        self.write_calls.append(index)

    def deleteChannel(self, index: int) -> None:  # noqa: N802
        self.delete_calls.append(index)
        self.channels.pop(index)
        while len(self.channels) < len(self._live_channels):
            next_index = len(self.channels)
            self.channels.append(_FakeChannel(index=next_index, role=_FakeRole.DISABLED))
        for idx, channel in enumerate(self.channels):
            channel.index = idx


class _FakeIface:
    def __init__(self, node: _FakeNode) -> None:
        self.localNode = node


class _FakeLock:
    def __init__(self) -> None:
        self.depth = 0

    def acquire(self) -> None:
        self.depth += 1

    def release(self) -> None:
        self.depth -= 1


def test_upsert_channel_uses_settings_transaction_and_verifies_radio_refresh(monkeypatch) -> None:
    node = _FakeNode()
    iface = _FakeIface(node)
    lock = _FakeLock()

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    monkeypatch.setattr("meshdash.services_channels.fromPSK", None, raising=False)

    request = ChannelSettingsRequest(
        action="upsert",
        channel_index=2,
        role="SECONDARY",
        settings={
            "name": "Meshyface",
            "psk": "base64:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "uplink_enabled": False,
            "downlink_enabled": False,
        },
    )

    response = apply_channel_settings(
        request,
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response["ok"] is True
    assert response["channel_index"] == 2
    assert response["role"] == "SECONDARY"
    assert node.write_calls == [2]
    assert node.transaction_open is False
    assert node.channels[2].role == _FakeRole.SECONDARY
    assert node.channels[2].settings.name == "Meshyface"


def test_upsert_rejects_channel_names_longer_than_meshtastic_limit(monkeypatch) -> None:
    node = _FakeNode()
    iface = _FakeIface(node)
    lock = _FakeLock()

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    request = ChannelSettingsRequest(
        action="upsert",
        channel_index=2,
        role="SECONDARY",
        settings={"name": "Meshyface Beta"},
    )

    response = apply_channel_settings(
        request,
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response["ok"] is False
    assert response["error"] == "Channel name must be 10 characters or fewer"
    assert node.write_calls == []


def test_disable_channel_clears_last_slot_in_place(monkeypatch) -> None:
    node = _FakeNode()
    node._live_channels = [
        _FakeChannel(index=0, role=_FakeRole.PRIMARY, psk=b"default"),
        _FakeChannel(index=1, role=_FakeRole.SECONDARY, name="test", psk=b"default"),
        _FakeChannel(index=2, role=_FakeRole.SECONDARY, name="Meshyface", psk=b"secret"),
        _FakeChannel(index=3, role=_FakeRole.DISABLED),
    ]
    node.channels = _clone_channels(node._live_channels)
    iface = _FakeIface(node)
    lock = _FakeLock()

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    response = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=2),
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response["ok"] is True
    assert node.delete_calls == []
    assert node.write_calls == [2]
    assert node.channels[1].settings.name == "test"
    assert node.channels[2].role == _FakeRole.DISABLED
    assert node.channels[2].settings.name == ""


def test_disable_last_secondary_channel_clears_slot_in_place(monkeypatch) -> None:
    node = _FakeNode()
    iface = _FakeIface(node)
    lock = _FakeLock()

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    response = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response["ok"] is True
    assert node.delete_calls == []
    assert node.write_calls == [1]
    assert node.channels[1].role == _FakeRole.DISABLED
    assert node.channels[1].settings.name == ""


def test_upsert_new_channel_defaults_psk_instead_of_reusing_disabled_slot_secret(monkeypatch) -> None:
    node = _FakeNode()
    node._live_channels = [
        _FakeChannel(index=0, role=_FakeRole.PRIMARY, psk=b"default"),
        _FakeChannel(index=1, role=_FakeRole.DISABLED, name="old", psk=b"stale-secret"),
        _FakeChannel(index=2, role=_FakeRole.DISABLED),
        _FakeChannel(index=3, role=_FakeRole.DISABLED),
    ]
    node.channels = _clone_channels(node._live_channels)
    iface = _FakeIface(node)
    lock = _FakeLock()

    fake_meshtastic = ModuleType("meshtastic")
    fake_util = ModuleType("meshtastic.util")
    fake_util.fromPSK = lambda value: f"psk:{value}".encode("utf-8")
    fake_meshtastic.util = fake_util

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    monkeypatch.setitem(sys.modules, "meshtastic", fake_meshtastic)
    monkeypatch.setitem(sys.modules, "meshtastic.util", fake_util)

    response = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            role="SECONDARY",
            settings={"name": "fresh"},
        ),
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response["ok"] is True
    assert node.channels[1].settings.psk == b"psk:default"
    assert "settings.psk" in response["applied_fields"]


def test_import_channel_url_normalizes_add_only_and_uses_getnode_fallback(monkeypatch) -> None:
    node = _FakeNode()
    delattr(node, "channels")
    imported: list[tuple[str, bool]] = []

    def _set_url(url: str, addOnly: bool = False) -> None:  # noqa: N803
        imported.append((url, addOnly))

    node.setURL = _set_url  # type: ignore[attr-defined]
    iface = SimpleNamespace(getNode=lambda node_id: node)
    lock = _FakeLock()

    response = apply_channel_settings(
        ChannelSettingsRequest(
            action="import_url",
            url="https://meshtastic.org/e/#abc",
            add_only=True,
        ),
        iface=iface,
        send_lock=lock,
        show_secrets=False,
    )

    assert response == {
        "ok": True,
        "action": "import_url",
        "add_only": True,
        "reboot_expected": True,
    }
    assert imported == [("https://meshtastic.org/e/?add=true#abc", True)]
    assert lock.depth == 0
    assert len(node.channels) == 4


def test_export_channel_url_requires_secret_visibility_and_device_support() -> None:
    node = _FakeNode()
    iface = _FakeIface(node)

    hidden = apply_channel_settings(
        ChannelSettingsRequest(action="export_url"),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=False,
    )
    unsupported = apply_channel_settings(
        ChannelSettingsRequest(action="export_url"),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    node.getURL = lambda *, includeAll=True: f"url:{includeAll}"  # type: ignore[attr-defined]
    exported = apply_channel_settings(
        ChannelSettingsRequest(action="export_url", include_all=False),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )

    assert hidden["ok"] is False
    assert "Secrets are redacted" in hidden["error"]
    assert unsupported == {"ok": False, "error": "Meshtastic node does not support getURL()"}
    assert exported == {
        "ok": True,
        "action": "export_url",
        "include_all": False,
        "url": "url:False",
    }


def test_channel_settings_reports_setup_and_capability_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        "meshdash.services_channels._import_channel_pb2",
        lambda: (_ for _ in ()).throw(RuntimeError("protobuf missing")),
    )
    protobuf_error = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1),
        iface=_FakeIface(_FakeNode()),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    missing_channels = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1),
        iface=SimpleNamespace(localNode=object()),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    node_without_writer = SimpleNamespace(channels=_FakeNode().channels)
    no_writer = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1),
        iface=SimpleNamespace(localNode=node_without_writer),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    assert protobuf_error["error"] == "Meshtastic channel protobuf unavailable: protobuf missing"
    assert missing_channels["error"] == "Channels unavailable: Channels are not loaded"
    assert no_writer == {"ok": False, "error": "Meshtastic node does not support writeChannel()"}


@pytest.mark.parametrize(
    ("channel_request", "error"),
    [
        (ChannelSettingsRequest(action="disable"), "channel_index is required for disable"),
        (ChannelSettingsRequest(action="disable", channel_index=0), "Primary channel (index 0) cannot be disabled"),
        (
            ChannelSettingsRequest(action="disable", channel_index=99),
            "Disable channels from the end (highest active index) to avoid gaps",
        ),
        (ChannelSettingsRequest(action="upsert", channel_index=99), "channel_index out of range"),
        (ChannelSettingsRequest(action="upsert", channel_index=2, role="PRIMARY"), "Only index 0 can be PRIMARY"),
        (ChannelSettingsRequest(action="upsert", channel_index=1, role="DISABLED"), "Use action=disable"),
        (ChannelSettingsRequest(action="upsert", channel_index=1, role="bogus"), "Invalid role"),
    ],
)
def test_channel_settings_rejects_invalid_disable_and_role_requests(monkeypatch, channel_request, error) -> None:
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    response = apply_channel_settings(
        channel_request,
        iface=_FakeIface(_FakeNode()),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    assert response["ok"] is False
    assert str(response["error"]).startswith(error)


def test_upsert_rejects_nonconsecutive_new_channel_and_empty_name(monkeypatch) -> None:
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    node = _FakeNode()

    nonconsecutive = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=3, settings={"name": "skip"}),
        iface=_FakeIface(node),
        send_lock=_FakeLock(),
        show_secrets=False,
    )
    empty_name = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=2, settings={"name": ""}),
        iface=_FakeIface(node),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    assert nonconsecutive["error"] == "Channels must be consecutive. Add the next available channel slot."
    assert nonconsecutive["next_available_index"] == 2
    assert empty_name["error"] == "Channel name is required when adding a channel"


def test_upsert_applies_module_settings_and_preserves_redacted_psk(monkeypatch) -> None:
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    node = _FakeNode()
    node.channels[1].settings.psk = b"existing"
    iface = _FakeIface(node)

    response = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            settings={
                "psk": "<redacted>",
                "module_settings": {
                    "is_muted": True,
                    "position_precision": "18",
                },
            },
        ),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    assert response["ok"] is True
    assert node.channels[1].settings.psk == b"existing"
    assert node.channels[1].module_settings.is_muted is True
    assert node.channels[1].module_settings.position_precision == 18
    assert "settings.psk" in response["ignored_fields"]
    assert "module_settings.is_muted" in response["applied_fields"]
    assert "module_settings.position_precision" in response["applied_fields"]


def test_channel_settings_reports_write_and_verification_failures(monkeypatch) -> None:
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    class _BadWriteNode(_FakeNode):
        def writeChannel(self, index: int) -> None:  # noqa: N802
            raise RuntimeError(f"bad channel {index}")

    write_failed = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, settings={"name": "new"}),
        iface=_FakeIface(_BadWriteNode()),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    node = _FakeNode()
    original_write = node.writeChannel

    def _write_and_disable(index: int) -> None:
        original_write(index)
        node.channels[index].role = _FakeRole.DISABLED

    node.writeChannel = _write_and_disable  # type: ignore[method-assign]
    verification_failed = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, settings={"name": "new"}),
        iface=_FakeIface(node),
        send_lock=_FakeLock(),
        show_secrets=False,
    )

    assert write_failed["error"] == "Write failed: bad channel 1"
    assert write_failed["applied_fields"] == ["settings.name"]
    assert verification_failed["error"] == "Write verification failed: channel remained disabled on radio"
