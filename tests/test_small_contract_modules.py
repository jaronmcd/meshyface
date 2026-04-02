from meshdash.config import DEFAULT_ROOMS_PORTNUM
from meshdash.rooms.constants import ROOMS_PORTNUM_DEFAULT, ROOMS_SCHEMA_VERSION
from meshdash.runtime_lifecycle_contracts import CloseableResource, RuntimeServer


def test_rooms_constants_align_with_config_default():
    assert ROOMS_PORTNUM_DEFAULT == DEFAULT_ROOMS_PORTNUM
    assert isinstance(ROOMS_SCHEMA_VERSION, int)
    assert ROOMS_SCHEMA_VERSION >= 1


def test_runtime_lifecycle_protocols_expose_expected_members():
    assert "serve_forever" in RuntimeServer.__dict__
    assert "server_close" in RuntimeServer.__dict__
    assert "close" in CloseableResource.__dict__
