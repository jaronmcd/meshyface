import time
from typing import Optional

from .revision import RevisionInfo
from .runtime_state_contracts import StateSnapshotRuntimeDependencies
from .runtime_state_dependencies import (
    build_state_snapshot_runtime_dependencies_from_legacy_args,
)
from .runtime_types import BuildStateFn, StateFn
from .state_service_contracts import StateTracker

from .helpers import to_jsonable as _to_jsonable
from .helpers_security import redact_secrets as _redact_secrets
from .state_node_rows import collect_nodes_typed as _collect_nodes_typed
from .state_nodes import collect_local_state as _collect_local_state


def build_state_snapshot_loader(
    *,
    iface: object,
    tracker: StateTracker,
    started_at: float,
    target: str,
    show_secrets: bool,
    storage_probe_path: Optional[str],
    revision_info: RevisionInfo,
    build_state_fn: BuildStateFn,
) -> StateFn:
    dependencies = build_state_snapshot_runtime_dependencies_from_legacy_args(
        iface=iface,
        tracker=tracker,
        started_at=started_at,
        target=target,
        show_secrets=show_secrets,
        storage_probe_path=storage_probe_path,
        revision_info=revision_info,
    )
    return build_state_snapshot_loader_with_dependencies(
        dependencies=dependencies,
        build_state_fn=build_state_fn,
    )


def build_state_snapshot_loader_with_dependencies(
    *,
    dependencies: StateSnapshotRuntimeDependencies,
    build_state_fn: BuildStateFn,
) -> StateFn:
    def _live_packet_rev() -> int:
        """Best-effort revision token that increments when packets are observed."""
        raw = getattr(dependencies.tracker, "live_packet_count", 0)
        try:
            return int(raw or 0)
        except Exception:
            return 0

    def _radio_link_rev() -> int:
        """Revision token that bumps when radio link state changes."""
        raw = getattr(dependencies.tracker, "radio_link_changed_unix", 0)
        try:
            return int(raw or 0)
        except Exception:
            return 0

    def _time_bucket(seconds: int = 60) -> int:
        return int(time.time() // max(1, seconds))

    def _cache_key() -> tuple[int, int, int]:
        # Include a slow time bucket so "slow-changing" summary values like
        # uptime/disk can refresh occasionally even if the mesh is quiet.
        # Also include radio link revision so disconnect/reconnect state appears
        # immediately without waiting for the time bucket to roll.
        return (_live_packet_rev(), _radio_link_rev(), _time_bucket(60))

    def _etag_for(variant: str) -> str:
        packet_rev, radio_rev, bucket = _cache_key()
        return f'W/"{variant}-p{packet_rev}-r{radio_rev}-t{bucket}"'

    full_cache_key: tuple[int, int, int] | None = None
    full_cache_payload: dict[str, object] | None = None

    def state_fn() -> dict:
        nonlocal full_cache_key, full_cache_payload
        key = _cache_key()
        if full_cache_payload is not None and full_cache_key == key:
            return full_cache_payload
        payload = build_state_fn(
            iface=dependencies.iface,
            tracker=dependencies.tracker,
            started_at=dependencies.started_at,
            target=dependencies.target,
            show_secrets=dependencies.show_secrets,
            storage_probe_path=dependencies.storage_probe_path,
            revision_info=dependencies.revision_info,
        )
        full_cache_key = key
        full_cache_payload = payload
        return payload

    def state_fn_etag() -> str:
        return _etag_for("full")

    try:
        setattr(state_fn, "etag", state_fn_etag)
    except Exception:
        pass

    # Optional fast-path for lite polling: if the build_state_fn was wrapped
    # with a `.lite` variant during wiring, expose it here too.
    build_state_lite = getattr(build_state_fn, "lite", None)
    if callable(build_state_lite):
        lite_cache_key: tuple[int, int, int] | None = None
        lite_cache_payload: dict[str, object] | None = None

        def state_fn_lite() -> dict:
            nonlocal lite_cache_key, lite_cache_payload
            key = _cache_key()
            if lite_cache_payload is not None and lite_cache_key == key:
                return lite_cache_payload
            payload = build_state_lite(
                iface=dependencies.iface,
                tracker=dependencies.tracker,
                started_at=dependencies.started_at,
                target=dependencies.target,
                show_secrets=dependencies.show_secrets,
                storage_probe_path=dependencies.storage_probe_path,
                revision_info=dependencies.revision_info,
            )
            lite_cache_key = key
            lite_cache_payload = payload
            return payload

        def state_fn_lite_etag() -> str:
            return _etag_for("lite")

        try:
            setattr(state_fn_lite, "etag", state_fn_lite_etag)
        except Exception:
            pass

        try:
            setattr(state_fn, "lite", state_fn_lite)
        except Exception:
            pass

    # Optional raw/debug getters used by the Data view.
    sensitive_field_names = getattr(build_state_fn, "_sensitive_field_names", set())
    if not isinstance(sensitive_field_names, set):
        try:
            sensitive_field_names = set(sensitive_field_names)
        except Exception:
            sensitive_field_names = set()

    def _maybe_redact(value: object) -> object:
        if dependencies.show_secrets:
            return value
        return _redact_secrets(value, sensitive_field_names)

    def raw_my_info() -> dict[str, object]:
        return _maybe_redact(_to_jsonable(getattr(dependencies.iface, "myInfo", None)))  # type: ignore[return-value]

    def raw_metadata() -> dict[str, object]:
        return _maybe_redact(_to_jsonable(getattr(dependencies.iface, "metadata", None)))  # type: ignore[return-value]

    def raw_local_state() -> dict[str, object]:
        return _maybe_redact(_collect_local_state(dependencies.iface))  # type: ignore[return-value]

    def raw_nodes_full() -> list[dict[str, object]]:
        nodes = _collect_nodes_typed(dependencies.iface)
        return _maybe_redact(nodes.full)  # type: ignore[return-value]

    try:
        setattr(state_fn, "raw_my_info", raw_my_info)
        setattr(state_fn, "raw_metadata", raw_metadata)
        setattr(state_fn, "raw_local_state", raw_local_state)
        setattr(state_fn, "raw_nodes_full", raw_nodes_full)
    except Exception:
        pass

    return state_fn
