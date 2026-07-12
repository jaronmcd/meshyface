from types import SimpleNamespace

import pytest

import mesh_connection


class _FakeTcpInterfaceModule:
    calls: list[dict[str, object]] = []

    @classmethod
    def TCPInterface(cls, **kwargs: object) -> object:
        cls.calls.append(dict(kwargs))
        return object()


class _FakeSerialInterfaceModule:
    @staticmethod
    def SerialInterface(**_kwargs: object) -> object:
        return object()


def _args(host: str, *, allow: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        mesh_host=host,
        mesh_tcp_port=4403,
        mesh_port="/dev/ttyUSB0",
        allow_insecure_mesh_tcp=allow,
    )


def test_remote_mesh_tcp_requires_explicit_insecure_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(mesh_connection, "_meshtastic_tcp_interface", _FakeTcpInterfaceModule)
    monkeypatch.setattr(
        mesh_connection,
        "_meshtastic_serial_interface",
        _FakeSerialInterfaceModule,
    )

    with pytest.raises(RuntimeError, match="Refusing unauthenticated Meshtastic TCP"):
        mesh_connection.open_mesh_interface(_args("192.0.2.10"))

    mesh_connection.open_mesh_interface(_args("192.0.2.10", allow=True))
    assert _FakeTcpInterfaceModule.calls[-1] == {
        "hostname": "192.0.2.10",
        "portNumber": 4403,
    }


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "[::1]"])
def test_loopback_mesh_tcp_is_allowed_without_opt_in(monkeypatch, host: str) -> None:
    monkeypatch.setattr(mesh_connection, "_meshtastic_tcp_interface", _FakeTcpInterfaceModule)
    monkeypatch.setattr(
        mesh_connection,
        "_meshtastic_serial_interface",
        _FakeSerialInterfaceModule,
    )

    mesh_connection.open_mesh_interface(_args(host))
