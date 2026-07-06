from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

PACK_FORMAT = "meshdash-map-pack/1"

_PACKS_DIR_ENV = "MESH_DASHBOARD_MAP_PACKS_DIR"
_DEFAULT_PACKS_DIR = "map_packs"

_PACK_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_CHUNK_PATH_RE = re.compile(r"^chunks/[a-z0-9_]{1,64}/[a-z0-9_.-]{1,80}\.json$")

_DOWNLOAD_CHUNK_BYTES = 256 * 1024
_DOWNLOAD_TIMEOUT_SECONDS = 30.0
_MAX_PACK_ZIP_BYTES = 600 * 1024 * 1024
_MAX_INSTALLED_PACK_BYTES = 600 * 1024 * 1024
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024

KNOWN_PACKS: dict[str, dict[str, Any]] = {
    "global_detail": {
        "label": "Global Detail",
        "description": (
            "Natural Earth 1:10m global vector detail (coastline, borders, "
            "states, rivers, lakes, urban areas, roads, railroads, parks) "
            "plus GeoNames cities500 place labels with state/country names. "
            "Roughly 140 MB installed."
        ),
        "download_url_env": "MESH_DASHBOARD_MAP_PACK_URL_GLOBAL_DETAIL",
        "download_url": (
            "https://github.com/jaronmcd/meshyface/releases/download/"
            "map-pack-global-detail-v1/mesh_map_pack_global_detail_v1.zip"
        ),
        "download_bytes_estimate": 30 * 1024 * 1024,
    },
}

def map_packs_dir() -> Path:
    override = str(os.environ.get(_PACKS_DIR_ENV) or "").strip()
    if override:
        return Path(override)
    return Path(_DEFAULT_PACKS_DIR)


def _clean_pack_id(value: object) -> str:
    pack_id = str(value or "").strip().lower()
    if not _PACK_ID_RE.fullmatch(pack_id):
        return ""
    return pack_id


def _pack_install_dir(pack_id: str) -> Path:
    return map_packs_dir() / pack_id


def _pack_sideload_zip(pack_id: str) -> Path:
    return map_packs_dir() / f"{pack_id}.zip"


def _installer_script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "install_map_pack.py"


def _installer_command_prefix() -> str:
    return " ".join(
        shlex.quote(str(arg))
        for arg in (sys.executable or "python", str(_installer_script_path()))
    )


def _installer_command(pack_id: str, *, sideload_ready: bool) -> str:
    args = [
        pack_id,
        "--packs-dir",
        str(map_packs_dir().resolve()),
    ]
    if not sideload_ready:
        args.append("--download")
    quoted = " ".join(shlex.quote(str(arg)) for arg in args)
    return f"{_installer_command_prefix()} {quoted}"


def pack_download_url(pack_id: str) -> str:
    known = KNOWN_PACKS.get(pack_id)
    if not isinstance(known, dict):
        return ""
    env_name = str(known.get("download_url_env") or "").strip()
    if env_name:
        override = str(os.environ.get(env_name) or "").strip()
        if override:
            return override
    return str(known.get("download_url") or "").strip()


def _validate_manifest_obj(manifest: object, expected_pack_id: str = "") -> str:
    """Return an error string, or empty string when the manifest is valid."""
    if not isinstance(manifest, dict):
        return "manifest is not an object"
    if str(manifest.get("format") or "") != PACK_FORMAT:
        return f"unsupported pack format: {manifest.get('format')!r}"
    pack_id = _clean_pack_id(manifest.get("id"))
    if not pack_id:
        return "manifest has no valid pack id"
    if expected_pack_id and pack_id != expected_pack_id:
        return f"manifest id {pack_id!r} does not match expected {expected_pack_id!r}"
    layers = manifest.get("layers")
    if not isinstance(layers, dict) or not layers:
        return "manifest has no layers"
    for layer_name, layer in layers.items():
        if not isinstance(layer, dict):
            return f"layer {layer_name!r} is not an object"
        chunks = layer.get("chunks")
        if not isinstance(chunks, dict):
            return f"layer {layer_name!r} has no chunks object"
        for cell_id, chunk in chunks.items():
            if not isinstance(chunk, dict):
                return f"chunk {layer_name}/{cell_id} is not an object"
            path = str(chunk.get("path") or "")
            if not _CHUNK_PATH_RE.fullmatch(path):
                return f"chunk {layer_name}/{cell_id} has unsafe path {path!r}"
    return ""


def load_installed_manifest(pack_id: str) -> Optional[dict[str, Any]]:
    clean_id = _clean_pack_id(pack_id)
    if not clean_id:
        return None
    manifest_path = _pack_install_dir(clean_id) / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if _validate_manifest_obj(manifest, clean_id):
        return None
    return manifest


def _fail_install(staging_dir: Path, message: str) -> str:
    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
    except Exception:
        pass
    return message


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _zip_member_info(archive: Any, rel_path: str):
    try:
        return archive.getinfo(rel_path)
    except KeyError:
        return None


def _read_zip_member_limited(archive: Any, rel_path: str, max_bytes: int) -> bytes:
    """Read a zip member with an explicit decompressed byte ceiling."""
    limit = max(0, int(max_bytes))
    info = _zip_member_info(archive, rel_path)
    if info is None:
        raise KeyError(rel_path)
    if int(getattr(info, "file_size", 0) or 0) > limit:
        raise ValueError(f"zip member {rel_path} exceeds size limit")
    chunks: list[bytes] = []
    total = 0
    with archive.open(info) as handle:
        while True:
            block = handle.read(min(_DOWNLOAD_CHUNK_BYTES, max(1, limit - total + 1)))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise ValueError(f"zip member {rel_path} exceeds size limit")
            chunks.append(block)
    return b"".join(chunks)


def install_pack_zip(pack_id: str, zip_path: Path) -> str:
    """Validate and install a pack zip. Returns an error string or ""."""
    import zipfile

    pack_id = _clean_pack_id(pack_id)
    if not pack_id:
        return "invalid pack id"
    packs_dir = map_packs_dir()
    staging_dir = packs_dir / f".install-{pack_id}.tmp"
    try:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            try:
                manifest_raw = _read_zip_member_limited(
                    archive, "manifest.json", _MAX_MANIFEST_BYTES
                )
                manifest = json.loads(manifest_raw.decode("utf-8"))
            except KeyError:
                return _fail_install(staging_dir, "pack zip has no manifest.json")
            except Exception as exc:
                return _fail_install(staging_dir, f"pack manifest unreadable: {exc}")
            manifest_error = _validate_manifest_obj(manifest, pack_id)
            if manifest_error:
                return _fail_install(staging_dir, manifest_error)
            declared_total_bytes = _safe_int(manifest.get("total_bytes"), 0)
            if declared_total_bytes < 0:
                return _fail_install(staging_dir, "pack manifest has invalid total_bytes")
            if declared_total_bytes > _MAX_INSTALLED_PACK_BYTES:
                return _fail_install(staging_dir, "pack exceeds installed size limit")
            (staging_dir / "manifest.json").write_bytes(manifest_raw)
            layers = manifest.get("layers") or {}
            manifest_chunk_count = 0
            for layer in layers.values():
                chunks = layer.get("chunks") if isinstance(layer, dict) else None
                if isinstance(chunks, dict):
                    manifest_chunk_count += len(chunks)
            if manifest_chunk_count > 0 and declared_total_bytes <= 0:
                return _fail_install(staging_dir, "pack manifest has invalid total_bytes")
            installed_bytes = 0
            for layer_name, layer in layers.items():
                chunks = layer.get("chunks") or {}
                for cell_id, chunk in chunks.items():
                    rel_path = str(chunk.get("path") or "")
                    declared_chunk_bytes = _safe_int(chunk.get("bytes"), -1)
                    if declared_chunk_bytes < 0:
                        return _fail_install(
                            staging_dir,
                            f"chunk {rel_path} has invalid byte count",
                        )
                    if declared_chunk_bytes > _MAX_INSTALLED_PACK_BYTES:
                        return _fail_install(
                            staging_dir,
                            f"chunk {rel_path} exceeds size limit",
                        )
                    installed_bytes += declared_chunk_bytes
                    if installed_bytes > _MAX_INSTALLED_PACK_BYTES:
                        return _fail_install(
                            staging_dir,
                            "pack exceeds installed size limit",
                        )
                    try:
                        info = _zip_member_info(archive, rel_path)
                        if info is None:
                            raise KeyError(rel_path)
                        if int(getattr(info, "file_size", 0) or 0) != declared_chunk_bytes:
                            return _fail_install(
                                staging_dir,
                                f"chunk {rel_path} byte count does not match manifest",
                            )
                        payload = _read_zip_member_limited(
                            archive, rel_path, declared_chunk_bytes
                        )
                    except KeyError:
                        return _fail_install(
                            staging_dir, f"pack zip is missing chunk {rel_path}"
                        )
                    except Exception as exc:
                        return _fail_install(
                            staging_dir, f"chunk {rel_path} unreadable: {exc}"
                        )
                    if len(payload) != declared_chunk_bytes:
                        return _fail_install(
                            staging_dir,
                            f"chunk {rel_path} byte count does not match manifest",
                        )
                    expected_sha = str(chunk.get("sha256") or "").strip().lower()
                    if expected_sha:
                        actual_sha = hashlib.sha256(payload).hexdigest()
                        if actual_sha != expected_sha:
                            return _fail_install(
                                staging_dir,
                                f"chunk {rel_path} failed checksum verification",
                            )
                    target = staging_dir / rel_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
            if installed_bytes != declared_total_bytes:
                return _fail_install(
                    staging_dir,
                    "pack installed byte count does not match manifest",
                )
    except Exception as exc:
        return _fail_install(staging_dir, f"pack install failed: {exc}")

    install_dir = _pack_install_dir(pack_id)
    try:
        if install_dir.exists():
            shutil.rmtree(install_dir)
        os.replace(staging_dir, install_dir)
    except Exception as exc:
        try:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
        except Exception:
            pass
        return f"pack install failed while activating: {exc}"
    return ""


def remove_installed_pack(pack_id_raw: object) -> str:
    """Remove an installed pack directory. Returns an error string or ""."""
    pack_id = _clean_pack_id(pack_id_raw)
    if not pack_id:
        return "invalid pack id"
    install_dir = _pack_install_dir(pack_id)
    if not install_dir.exists():
        return "pack is not installed"
    try:
        shutil.rmtree(install_dir)
    except Exception as exc:
        return f"failed to delete pack: {exc}"
    return ""


def _installed_pack_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    layers = manifest.get("layers")
    layer_names = list(layers.keys()) if isinstance(layers, dict) else []
    chunk_count = 0
    if isinstance(layers, dict):
        for layer in layers.values():
            chunks = layer.get("chunks") if isinstance(layer, dict) else None
            if isinstance(chunks, dict):
                chunk_count += len(chunks)
    try:
        total_bytes = int(manifest.get("total_bytes") or 0)
    except (TypeError, ValueError):
        total_bytes = 0
    try:
        version = int(manifest.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    return {
        "version": version,
        "label": str(manifest.get("label") or ""),
        "attribution": str(manifest.get("attribution") or ""),
        "total_bytes": total_bytes,
        "layers": layer_names,
        "chunk_count": chunk_count,
    }


def map_pack_status_payload() -> dict[str, Any]:
    packs_dir = map_packs_dir()
    pack_ids: list[str] = list(KNOWN_PACKS.keys())
    try:
        if packs_dir.is_dir():
            for entry in sorted(packs_dir.iterdir()):
                if entry.is_dir() and not entry.name.startswith("."):
                    pack_id = _clean_pack_id(entry.name)
                    if pack_id and pack_id not in pack_ids:
                        pack_ids.append(pack_id)
                elif entry.is_file() and entry.suffix == ".zip":
                    pack_id = _clean_pack_id(entry.stem)
                    if pack_id and pack_id not in pack_ids:
                        pack_ids.append(pack_id)
    except Exception:
        pass

    packs: list[dict[str, Any]] = []
    for pack_id in pack_ids:
        known = KNOWN_PACKS.get(pack_id) or {}
        manifest = load_installed_manifest(pack_id)
        sideload_ready = False
        try:
            sideload_zip = _pack_sideload_zip(pack_id)
            sideload_ready = sideload_zip.exists() and sideload_zip.stat().st_size > 0
        except Exception:
            sideload_ready = False

        if manifest is not None:
            state = "installed"
        elif sideload_ready:
            state = "sideload_ready"
        else:
            state = "not_installed"

        entry: dict[str, Any] = {
            "id": pack_id,
            "label": str(known.get("label") or (manifest or {}).get("label") or pack_id),
            "description": str(
                known.get("description") or (manifest or {}).get("description") or ""
            ),
            "state": state,
            "installed": manifest is not None,
            "sideload_ready": sideload_ready,
            "download_bytes_estimate": int(known.get("download_bytes_estimate") or 0),
            "install_command": _installer_command(
                pack_id, sideload_ready=sideload_ready
            ),
        }
        if manifest is not None:
            entry["installed_pack"] = _installed_pack_summary(manifest)
        packs.append(entry)

    return {
        "ok": True,
        "packs": packs,
        "packs_dir": str(packs_dir),
        "packs_dir_resolved": str(packs_dir.resolve()),
        "install_command_prefix": _installer_command_prefix(),
    }


def load_map_pack_manifest_payload(pack_id_raw: object) -> dict[str, Any]:
    pack_id = _clean_pack_id(pack_id_raw)
    if not pack_id:
        return {"ok": False, "error": "invalid pack id", "http_status": 400}
    manifest = load_installed_manifest(pack_id)
    if manifest is None:
        return {"ok": False, "error": "pack is not installed", "http_status": 404}
    payload = dict(manifest)
    payload["ok"] = True
    return payload


def read_map_pack_chunk(pack_id_raw: object, rel_path_raw: object) -> Optional[bytes]:
    pack_id = _clean_pack_id(pack_id_raw)
    rel_path = str(rel_path_raw or "")
    if not pack_id or not _CHUNK_PATH_RE.fullmatch(rel_path):
        return None
    install_dir = _pack_install_dir(pack_id)
    chunk_path = install_dir / rel_path
    try:
        resolved_root = install_dir.resolve(strict=True)
        resolved_chunk = chunk_path.resolve(strict=True)
    except Exception:
        return None
    if resolved_root not in resolved_chunk.parents:
        return None
    try:
        return chunk_path.read_bytes()
    except Exception:
        return None
