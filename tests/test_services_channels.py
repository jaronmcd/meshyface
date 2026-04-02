from types import SimpleNamespace
import sys
import types

import pytest

from meshdash.api_input_channels import ChannelSettingsRequest
from meshdash.services_channels import (
    _acquire_lock,
    _compute_last_active_index,
    _ensure_channels_loaded,
    _get_local_node,
    _role_name,
    _role_value,
    apply_channel_settings,
)


class _FakeRole:
    DISABLED = 0
    PRIMARY = 1
    SECONDARY = 2

    @classmethod
    def Name(cls, value: int) -> str:
        mapping = {
            cls.DISABLED: "DISABLED",
            cls.PRIMARY: "PRIMARY",
            cls.SECONDARY: "SECONDARY",
        }
        if int(value) not in mapping:
            raise ValueError("bad role")
        return mapping[int(value)]


class _FakeChannelPb2:
    class Channel:
        Role = _FakeRole


class _FakeSettings:
    def __init__(self):
        self.name = ""
        self.uplink_enabled = False
        self.downlink_enabled = False
        self.psk = b"existing"


class _FakeModuleSettings:
    def __init__(self):
        self.is_muted = False
        self.position_precision = 0


class _FakeChannel:
    def __init__(self, index: int, role: int):
        self.index = index
        self.role = role
        self.settings = _FakeSettings()
        self.module_settings = _FakeModuleSettings()


class _FakeNode:
    def __init__(
        self,
        *,
        channels,
        has_write_channel: bool = True,
        has_set_url: bool = True,
        write_error: Exception | None = None,
        export_url: str = "https://mesh.example/ch",
        export_error: Exception | None = None,
        set_url_error: Exception | None = None,
    ):
        self.channels = channels
        self.request_calls = []
        self.wait_calls = []
        self.write_calls = []
        self.set_url_calls = []
        self._write_error = write_error
        self._export_url = export_url
        self._export_error = export_error
        self._set_url_error = set_url_error
        if has_write_channel:
            self.writeChannel = self._write_channel
        if has_set_url:
            self.setURL = self._set_url

    def requestChannels(self, idx=0):
        self.request_calls.append(idx)
        if self.channels is None:
            self.channels = [_FakeChannel(0, _FakeRole.PRIMARY)]

    def waitForConfig(self, key):
        self.wait_calls.append(key)

    def _write_channel(self, idx: int):
        self.write_calls.append(int(idx))
        if self._write_error is not None:
            raise self._write_error

    def _set_url(self, url, addOnly=False):
        self.set_url_calls.append((str(url), bool(addOnly)))
        if self._set_url_error is not None:
            raise self._set_url_error

    def getURL(self, includeAll=True):
        if self._export_error is not None:
            raise self._export_error
        suffix = "all=1" if includeAll else "all=0"
        return f"{self._export_url}?{suffix}"


class _FakeLock:
    def __init__(self):
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self):
        self.acquire_calls += 1

    def release(self):
        self.release_calls += 1


def _iface_with_local(node):
    return SimpleNamespace(localNode=node)


def test_get_local_node_and_channel_helpers():
    local = object()
    assert _get_local_node(_iface_with_local(local)) is local

    fallback = object()
    iface = SimpleNamespace(localNode=None, getNode=lambda _id: fallback)
    assert _get_local_node(iface) is fallback

    with pytest.raises(RuntimeError, match="no local node"):
        _get_local_node(SimpleNamespace())

    eager_node = _FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY)])
    assert _ensure_channels_loaded(eager_node) is eager_node.channels

    lazy_node = _FakeNode(channels=None)
    loaded = _ensure_channels_loaded(lazy_node)
    assert isinstance(loaded, list)
    assert lazy_node.request_calls
    assert lazy_node.wait_calls == ["channels"]

    with pytest.raises(RuntimeError, match="not loaded"):
        _ensure_channels_loaded(SimpleNamespace(channels=None, requestChannels=None))


def test_role_last_active_and_lock_helpers():
    assert _role_value(_FakeChannelPb2, "primary") == _FakeRole.PRIMARY
    with pytest.raises(ValueError):
        _role_value(_FakeChannelPb2, "bad")

    assert _role_name(_FakeChannelPb2, 2) == "SECONDARY"
    broken_pb2 = SimpleNamespace(Channel=SimpleNamespace(Role=SimpleNamespace(Name=lambda _value: (_ for _ in ()).throw(ValueError("bad")))))
    assert _role_name(broken_pb2, 9) == "9"

    channels = [_FakeChannel(0, _FakeRole.PRIMARY), _FakeChannel(1, _FakeRole.SECONDARY), object()]
    assert _compute_last_active_index(_FakeChannelPb2, channels) == 1

    lock = _FakeLock()
    locked, release = _acquire_lock(lock)
    assert locked is True
    assert callable(release)
    release()
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1
    assert _acquire_lock(object()) == (False, None)


def test_apply_channel_settings_export_url_paths(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    node = _FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY)])

    hidden = apply_channel_settings(
        ChannelSettingsRequest(action="export_url", include_all=False),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=False,
    )
    assert hidden["ok"] is False

    no_get = apply_channel_settings(
        ChannelSettingsRequest(action="export_url"),
        iface=SimpleNamespace(localNode=SimpleNamespace(channels=node.channels)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert no_get["ok"] is False
    assert "getURL" in str(no_get["error"])

    fail_node = _FakeNode(channels=node.channels, export_error=RuntimeError("fail"))
    failed = apply_channel_settings(
        ChannelSettingsRequest(action="export_url"),
        iface=_iface_with_local(fail_node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert failed["ok"] is False
    assert "Export failed" in str(failed["error"])

    ok = apply_channel_settings(
        ChannelSettingsRequest(action="export_url", include_all=False),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert ok["ok"] is True
    assert ok["action"] == "export_url"
    assert ok["url"].endswith("all=0")


def test_apply_channel_settings_import_url_paths(monkeypatch):
    node = _FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY)])

    missing_support = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url="https://meshtastic.org/e/#A"),
        iface=SimpleNamespace(localNode=SimpleNamespace(channels=node.channels)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert missing_support["ok"] is False
    assert "setURL" in str(missing_support["error"])

    missing_url = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url=None),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert missing_url["ok"] is False
    assert "Missing url" in str(missing_url["error"])

    lock = _FakeLock()
    add_only_ok = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url="https://meshtastic.org/e/#AAAA", add_only=True),
        iface=_iface_with_local(node),
        send_lock=lock,
        show_secrets=True,
    )
    assert add_only_ok["ok"] is True
    assert node.set_url_calls[-1] == ("https://meshtastic.org/e/?add=true#AAAA", True)
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1

    join_ok = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url="https://meshtastic.org/e/?add=true#BBBB", add_only=False),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert join_ok["ok"] is True
    assert node.set_url_calls[-1] == ("https://meshtastic.org/e/#BBBB", False)

    fail = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url="https://meshtastic.org/e/#CCCC"),
        iface=_iface_with_local(_FakeNode(channels=node.channels, set_url_error=RuntimeError("boom"))),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert fail["ok"] is False
    assert "Import failed" in str(fail["error"])


def test_apply_channel_settings_import_url_supports_legacy_seturl_signature():
    class _LegacySetUrlNode:
        def __init__(self):
            self.channels = [_FakeChannel(0, _FakeRole.PRIMARY)]
            self.calls = []

        def setURL(self, url, add_only):  # positional-only style used by some versions
            self.calls.append((str(url), bool(add_only)))

    node = _LegacySetUrlNode()
    result = apply_channel_settings(
        ChannelSettingsRequest(action="import_url", url="https://meshtastic.org/e/#DDDD", add_only=True),
        iface=SimpleNamespace(localNode=node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert result["ok"] is True
    assert node.calls == [("https://meshtastic.org/e/?add=true#DDDD", True)]


def test_apply_channel_settings_disable_paths(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    channels = [_FakeChannel(0, _FakeRole.PRIMARY), _FakeChannel(1, _FakeRole.SECONDARY)]
    node = _FakeNode(channels=channels)
    iface = _iface_with_local(node)

    missing = apply_channel_settings(
        ChannelSettingsRequest(action="disable"),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert missing["ok"] is False
    assert "required" in str(missing["error"])

    bad_zero = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=0),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert bad_zero["ok"] is False

    out_of_order = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=2),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert out_of_order["ok"] is False
    assert out_of_order.get("last_active_index") == 1

    channels[1].role = _FakeRole.PRIMARY
    primary_block = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert primary_block["ok"] is False
    channels[1].role = _FakeRole.SECONDARY

    lock = _FakeLock()
    ok = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=iface,
        send_lock=lock,
        show_secrets=True,
    )
    assert ok["ok"] is True
    assert ok["action"] == "disable"
    assert node.write_calls == [1]
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1
    assert channels[1].role == _FakeRole.DISABLED


def test_apply_channel_settings_upsert_validation_and_success(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    channels = [
        _FakeChannel(0, _FakeRole.PRIMARY),
        _FakeChannel(1, _FakeRole.SECONDARY),
        _FakeChannel(2, _FakeRole.DISABLED),
        _FakeChannel(3, _FakeRole.DISABLED),
    ]
    node = _FakeNode(channels=channels)
    iface = _iface_with_local(node)

    unsupported = apply_channel_settings(
        ChannelSettingsRequest(action="unknown"),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert unsupported["ok"] is False

    out_of_range = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=99),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert out_of_range["ok"] is False
    assert "out of range" in str(out_of_range["error"])

    gap_error = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=3, settings={"name": "Late"}),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert gap_error["ok"] is False
    assert "consecutive" in str(gap_error["error"])

    bad_role = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, role="bad"),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert bad_role["ok"] is False

    no_fields = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert no_fields["ok"] is False
    assert "No valid fields" in str(no_fields["error"])

    need_name = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=2, settings={"name": ""}),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert need_name["ok"] is False
    assert "name is required" in str(need_name["error"])

    allow_unnamed = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=2,
            settings={"name": ""},
            allow_experimental=True,
        ),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert allow_unnamed["ok"] is True

    write_fail_node = _FakeNode(channels=channels, write_error=RuntimeError("write fail"))
    write_fail = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            settings={
                "name": "Ops",
                "uplink_enabled": True,
                "downlink_enabled": True,
                "psk": "<redacted>",
                "module_settings": {"is_muted": True, "position_precision": 3},
            },
        ),
        iface=_iface_with_local(write_fail_node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert write_fail["ok"] is False
    assert "Write failed" in str(write_fail["error"])
    assert write_fail["applied_fields"]

    success = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            settings={
                "name": "Ops",
                "uplink_enabled": True,
                "downlink_enabled": True,
                "psk": "<redacted>",
                "module_settings": {"is_muted": True, "position_precision": 3},
            },
        ),
        iface=iface,
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert success["ok"] is True
    assert success["action"] == "upsert"
    assert success["role"] == "SECONDARY"
    assert "settings.name" in success["applied_fields"]
    assert "settings.psk" in success["ignored_fields"]


def test_apply_channel_settings_handles_missing_protobuf_and_write_support(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: (_ for _ in ()).throw(RuntimeError("pb missing")))
    no_pb = apply_channel_settings(
        ChannelSettingsRequest(action="upsert"),
        iface=_iface_with_local(_FakeNode(channels=[])),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert no_pb["ok"] is False
    assert "protobuf unavailable" in str(no_pb["error"])

    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    no_write = apply_channel_settings(
        ChannelSettingsRequest(action="upsert"),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY)], has_write_channel=False)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert no_write["ok"] is False
    assert "writeChannel" in str(no_write["error"])


def test_channel_helpers_cover_request_typeerror_and_wait_errors():
    class _Node:
        def __init__(self):
            self.channels = None

        def requestChannels(self):
            self.channels = [_FakeChannel(0, _FakeRole.PRIMARY)]

        def waitForConfig(self, _name):
            raise RuntimeError("wait failed")

    loaded = _ensure_channels_loaded(_Node())
    assert isinstance(loaded, list)

    with pytest.raises(ValueError, match="empty"):
        _role_value(_FakeChannelPb2, "")

    class _Bad:
        index = object()
        role = _FakeRole.SECONDARY

    assert _compute_last_active_index(_FakeChannelPb2, [_FakeChannel(0, _FakeRole.PRIMARY), _Bad()]) == 0


def test_apply_channel_settings_disable_additional_error_paths(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    unavailable = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=_iface_with_local(SimpleNamespace(channels=None, requestChannels=None, waitForConfig=None, writeChannel=lambda _idx: None)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert unavailable["ok"] is False
    assert "Channels unavailable" in str(unavailable["error"])

    out_of_range_channels = [_FakeChannel(0, _FakeRole.PRIMARY), _FakeChannel(5, _FakeRole.SECONDARY)]
    out_of_range = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=5),
        iface=_iface_with_local(_FakeNode(channels=out_of_range_channels)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert out_of_range["ok"] is False
    assert "out of range" in str(out_of_range["error"])

    class _FlakyRoleChannel:
        def __init__(self):
            self.index = 1
            self._reads = 0
            self.settings = _BadSettings()
            self.module_settings = _BadModuleSettings()

        @property
        def role(self):
            self._reads += 1
            if self._reads == 1:
                return _FakeRole.SECONDARY
            return object()

        @role.setter
        def role(self, _value):
            raise RuntimeError("role locked")

    class _BadSettings:
        uplink_enabled = False
        downlink_enabled = False
        psk = b"existing"

        @property
        def name(self):
            return ""

        @name.setter
        def name(self, _value):
            raise RuntimeError("name blocked")

    class _BadModuleSettings:
        @property
        def is_muted(self):
            return False

        @is_muted.setter
        def is_muted(self, _value):
            raise RuntimeError("mute blocked")

        @property
        def position_precision(self):
            return 0

        @position_precision.setter
        def position_precision(self, _value):
            raise RuntimeError("precision blocked")

    disable_fail = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), _FlakyRoleChannel()], write_error=RuntimeError("write fail"))),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert disable_fail["ok"] is False
    assert "Write failed" in str(disable_fail["error"])


def test_apply_channel_settings_disable_sets_default_psk_when_util_available(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)
    fake_util = types.SimpleNamespace(fromPSK=lambda value: b"default-bytes")
    monkeypatch.setitem(sys.modules, "meshtastic.util", fake_util)

    channels = [_FakeChannel(0, _FakeRole.PRIMARY), _FakeChannel(1, _FakeRole.SECONDARY)]
    result = apply_channel_settings(
        ChannelSettingsRequest(action="disable", channel_index=1),
        iface=_iface_with_local(_FakeNode(channels=channels)),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert result["ok"] is True
    assert channels[1].settings.psk == b"default-bytes"


def test_apply_channel_settings_upsert_additional_branches(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    channels = [
        _FakeChannel(0, _FakeRole.PRIMARY),
        _FakeChannel(1, _FakeRole.SECONDARY),
        _FakeChannel(2, _FakeRole.DISABLED),
    ]
    node = _FakeNode(channels=channels)

    default_idx = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", settings={"name": "Auto"}),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert default_idx["ok"] is True
    assert default_idx["channel_index"] == 2

    primary_ok = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=0, settings={"name": "Primary"}),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert primary_ok["ok"] is True

    primary_reject = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, role="PRIMARY", settings={"name": "Bad"}),
        iface=_iface_with_local(node),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert primary_reject["ok"] is False

    class _RoleSetFailChannel(_FakeChannel):
        def __init__(self, index: int):
            self.index = index
            self.settings = _FakeSettings()
            self.module_settings = _FakeModuleSettings()

        @property
        def role(self):
            return _FakeRole.SECONDARY

        @role.setter
        def role(self, _value):
            raise RuntimeError("role set fail")

    role_set_fail = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, role="SECONDARY", settings={"name": "Ops"}),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), _RoleSetFailChannel(1)])),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert role_set_fail["ok"] is True

    class _RoleReadFailChannel(_FakeChannel):
        @property
        def role(self):
            return object()

        @role.setter
        def role(self, _value):
            pass

    with pytest.raises(TypeError):
        apply_channel_settings(
            ChannelSettingsRequest(action="upsert", channel_index=1, settings={"name": "Ops"}),
            iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), _RoleReadFailChannel(1, _FakeRole.SECONDARY)])),
            send_lock=_FakeLock(),
            show_secrets=True,
        )

    no_settings = apply_channel_settings(
        ChannelSettingsRequest(action="upsert", channel_index=1, settings={"name": "Ops"}),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), SimpleNamespace(index=1, role=_FakeRole.SECONDARY, settings=None)])),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert no_settings["ok"] is False
    assert "settings are unavailable" in str(no_settings["error"])


def test_apply_channel_settings_upsert_field_error_and_module_settings_paths(monkeypatch):
    monkeypatch.setattr("meshdash.services_channels._import_channel_pb2", lambda: _FakeChannelPb2)

    class _BadSettings:
        psk = b"existing"

        @property
        def name(self):
            return ""

        @name.setter
        def name(self, _value):
            raise RuntimeError("name fail")

        @property
        def uplink_enabled(self):
            return False

        @uplink_enabled.setter
        def uplink_enabled(self, _value):
            raise RuntimeError("uplink fail")

        @property
        def downlink_enabled(self):
            return False

        @downlink_enabled.setter
        def downlink_enabled(self, _value):
            raise RuntimeError("downlink fail")

    class _BadModuleSettings:
        @property
        def is_muted(self):
            return False

        @is_muted.setter
        def is_muted(self, _value):
            raise RuntimeError("mute fail")

        @property
        def position_precision(self):
            return 0

        @position_precision.setter
        def position_precision(self, _value):
            raise RuntimeError("precision fail")

    bad_channel = SimpleNamespace(
        index=1,
        role=_FakeRole.SECONDARY,
        settings=_BadSettings(),
        module_settings=_BadModuleSettings(),
    )

    fake_util = types.SimpleNamespace(fromPSK=lambda value: (_ for _ in ()).throw(RuntimeError("psk fail")))
    monkeypatch.setitem(sys.modules, "meshtastic.util", fake_util)

    result = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            settings={
                "name": "Ops",
                "uplink_enabled": True,
                "downlink_enabled": True,
                "psk": "custom",
                "module_settings": {"is_muted": True, "position_precision": 7},
            },
        ),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), bad_channel])),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert result["ok"] is False
    assert "No valid fields" in str(result["error"])
    assert "settings.name" in result["ignored_fields"]
    assert "settings.uplink_enabled" in result["ignored_fields"]
    assert "settings.downlink_enabled" in result["ignored_fields"]
    assert "settings.psk" in result["ignored_fields"]
    assert "module_settings.is_muted" in result["ignored_fields"]
    assert "module_settings.position_precision" in result["ignored_fields"]

    module_none_channel = SimpleNamespace(
        index=1,
        role=_FakeRole.SECONDARY,
        settings=_FakeSettings(),
        module_settings=None,
    )
    module_none = apply_channel_settings(
        ChannelSettingsRequest(
            action="upsert",
            channel_index=1,
            settings={"name": "Ops", "module_settings": {"is_muted": True}},
        ),
        iface=_iface_with_local(_FakeNode(channels=[_FakeChannel(0, _FakeRole.PRIMARY), module_none_channel])),
        send_lock=_FakeLock(),
        show_secrets=True,
    )
    assert module_none["ok"] is True
    assert "module_settings" in module_none["ignored_fields"]
