from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

PACK_FORMAT = "meshdash-map-pack/1"

_PACKS_DIR_ENV = "MESH_DASHBOARD_MAP_PACKS_DIR"
_DEFAULT_PACKS_DIR = "map_packs"

_PACK_ID_RE = re.compile(r"^[a-z0-9_]{1,64}$")
_CHUNK_PATH_RE = re.compile(r"^chunks/[a-z0-9_]{1,64}/[a-z0-9_.-]{1,80}\.json$")

_ZIP_READ_CHUNK_BYTES = 256 * 1024
_MAX_INSTALLED_PACK_BYTES = 600 * 1024 * 1024
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_MAX_BUILD_JOB_LINES = 240
_BUILD_JOB_TERMINATE_GRACE_SEC = 5.0

_MAP_PACK_BUILD_LAYERS = {
    "coastline",
    "borders",
    "states",
    "rivers",
    "lakes",
    "urban",
    "roads",
    "railroads",
    "parks",
    "peaks",
    "cities",
}
_MAP_PACK_BUILD_JOB_LOCK = threading.RLock()
_MAP_PACK_BUILD_JOB: dict[str, Any] | None = None


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


def _app_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _path_for_command(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    for base in (Path.cwd(), _app_dir()):
        try:
            rel_path = path.resolve().relative_to(base.resolve())
        except (OSError, ValueError):
            continue
        rel_text = rel_path.as_posix()
        return rel_text or "."
    return str(path)


def _shell_command_working_dir_prefix() -> str:
    try:
        cwd = str(Path.cwd().resolve())
    except OSError:
        cwd = str(Path.cwd())
    return f"cd {shlex.quote(cwd)} && "


def _python_command_path() -> str:
    app_dir = _app_dir()
    for rel_path in (Path(".venv/bin/python"), Path(".venv/Scripts/python.exe")):
        if (app_dir / rel_path).exists():
            return rel_path.as_posix()
    executable = str(sys.executable or "").strip()
    if not executable:
        return "python"
    command_path = _path_for_command(Path(executable))
    if Path(command_path).is_absolute():
        return "python"
    return command_path


def _script_command_prefix(script_name: str) -> str:
    args = (_python_command_path(), _path_for_command(_app_dir() / "scripts" / script_name))
    command = " ".join(shlex.quote(str(arg)) for arg in args)
    return f"{_shell_command_working_dir_prefix()}{command}"


def _packs_dir_command_path() -> str:
    return _path_for_command(map_packs_dir())


def _packs_dir_command_arg() -> str:
    return shlex.quote(_packs_dir_command_path())


def _installer_command_prefix() -> str:
    return _script_command_prefix("install_map_pack.py")


def _build_command_prefix() -> str:
    return _script_command_prefix("build_map_pack.py")


def _installer_command(pack_id: str) -> str:
    args = [
        pack_id,
        "--packs-dir",
        _packs_dir_command_path(),
    ]
    quoted = " ".join(shlex.quote(str(arg)) for arg in args)
    return f"{_installer_command_prefix()} {quoted}"


def _map_pack_error(message: str, *, code: str = "invalid_request") -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _string_value(value: object, max_len: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        text = text[:max_len].strip()
    return text


def _map_pack_build_pack_id(request: Mapping[str, object]) -> str:
    pack_id = _clean_pack_id(request.get("pack_id") or "mymesh")
    if not pack_id:
        raise ValueError(
            "pack_id must use lowercase letters, digits, or underscores"
        )
    return pack_id


def _map_pack_build_layers(request: Mapping[str, object]) -> list[str]:
    raw_layers = request.get("layers")
    if raw_layers in (None, ""):
        return []
    if isinstance(raw_layers, str):
        layers = [item.strip() for item in raw_layers.split(",")]
    elif isinstance(raw_layers, (list, tuple)):
        layers = [str(item or "").strip() for item in raw_layers]
    else:
        raise ValueError("layers must be a comma-separated string or list")
    clean_layers = [layer for layer in layers if layer]
    unknown = [layer for layer in clean_layers if layer not in _MAP_PACK_BUILD_LAYERS]
    if unknown:
        valid = ",".join(sorted(_MAP_PACK_BUILD_LAYERS))
        raise ValueError(f"unknown layers: {', '.join(unknown)} (valid: {valid})")
    deduped: list[str] = []
    for layer in clean_layers:
        if layer not in deduped:
            deduped.append(layer)
    return deduped


def _map_pack_build_radius_km(request: Mapping[str, object], *, required: bool) -> float:
    raw_radius = request.get("radius_km", request.get("radius"))
    if raw_radius in (None, ""):
        if required:
            raise ValueError("radius_km is required")
        return 0.0
    try:
        radius = float(raw_radius)
    except (TypeError, ValueError) as exc:
        raise ValueError("radius_km must be numeric") from exc
    if not (0.0 < radius <= 5000.0):
        raise ValueError("radius_km must be between 0 and 5000")
    return radius


def _map_pack_build_center(request: Mapping[str, object]) -> str:
    center = _string_value(request.get("center"), 80)
    parts = center.split(",", 1)
    if len(parts) != 2:
        raise ValueError("center must be LAT,LON")
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
    except ValueError as exc:
        raise ValueError("center must be numeric LAT,LON") from exc
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError("center is out of range")
    if lat == 0.0 and lon == 0.0:
        raise ValueError("center cannot be 0,0")
    return f"{lat:.4f},{lon:.4f}"


def _map_pack_build_argv(request_raw: object) -> tuple[list[str], dict[str, Any]]:
    if not isinstance(request_raw, Mapping):
        raise ValueError("request body must be an object")
    request: Mapping[str, object] = request_raw
    pack_id = _map_pack_build_pack_id(request)
    mode = _string_value(request.get("mode"), 24).lower()
    if not mode:
        if request.get("region") or request.get("city"):
            mode = "region"
        elif request.get("center"):
            mode = "center"
        else:
            mode = "history"
    if mode == "city":
        mode = "region"
    if mode not in {"center", "region", "history"}:
        raise ValueError("mode must be center, region, or history")

    script_path = _app_dir() / "scripts" / "build_map_pack.py"
    python_path = str(sys.executable or "").strip() or "python"
    argv = [
        python_path,
        str(script_path),
        "--source-dir",
        "map_sources",
        "--download",
    ]
    detail: dict[str, Any] = {
        "mode": mode,
        "pack_id": pack_id,
        "zip": f"{pack_id}.zip",
    }

    if mode == "region":
        region = _string_value(request.get("region") or request.get("city"), 120)
        if not region:
            raise ValueError("region or city is required")
        argv.extend(["--region", region])
        detail["region"] = region
    elif mode == "center":
        center = _map_pack_build_center(request)
        radius = _map_pack_build_radius_km(request, required=True)
        argv.extend(["--center", center, "--radius-km", f"{radius:.0f}"])
        detail["center"] = center
        detail["radius_km"] = int(round(radius))
    else:
        argv.append("--from-history")
        radius = _map_pack_build_radius_km(request, required=False)
        if radius > 0:
            argv.extend(["--radius-km", f"{radius:.0f}"])
            detail["radius_km"] = int(round(radius))

    layers = _map_pack_build_layers(request)
    if layers:
        argv.extend(["--layers", ",".join(layers)])
        detail["layers"] = layers
    if request.get("estimate") is True:
        argv.append("--estimate")
        detail["estimate"] = True
    argv.extend(["--pack-id", pack_id, "--zip", f"{pack_id}.zip"])
    return argv, detail


def _append_build_job_line(job: dict[str, Any], line: object) -> None:
    text = str(line or "").rstrip()
    if not text:
        return
    lines = job.setdefault("lines", [])
    lines.append(text)
    if len(lines) > _MAX_BUILD_JOB_LINES:
        del lines[: len(lines) - _MAX_BUILD_JOB_LINES]


def _build_job_payload(job: dict[str, Any] | None) -> dict[str, Any]:
    if not job:
        return {"ok": True, "active": False, "job": None}
    with _MAP_PACK_BUILD_JOB_LOCK:
        payload = {
            "ok": True,
            "active": str(job.get("status") or "") == "running",
            "job": {
                "id": str(job.get("id") or ""),
                "status": str(job.get("status") or ""),
                "pack_id": str(job.get("pack_id") or ""),
                "started_at": float(job.get("started_at") or 0.0),
                "finished_at": float(job.get("finished_at") or 0.0),
                "returncode": job.get("returncode"),
                "lines": list(job.get("lines") or []),
                "detail": dict(job.get("detail") or {}),
            },
        }
        error = job.get("error")
        if error:
            payload["job"]["error"] = str(error)
        return payload


def _finish_build_job(job: dict[str, Any], *, status: str, returncode: int | None) -> None:
    with _MAP_PACK_BUILD_JOB_LOCK:
        job["status"] = status
        job["returncode"] = returncode
        job["finished_at"] = time.time()
        if status == "succeeded":
            pack_id = str(job.get("pack_id") or "mymesh")
            _append_build_job_line(
                job,
                f"[map-pack] build complete: {pack_id}.zip",
            )


def _run_build_job(job: dict[str, Any]) -> None:
    process: subprocess.Popen[str] | None = None
    try:
        with _MAP_PACK_BUILD_JOB_LOCK:
            if bool(job.get("cancel_requested")):
                _finish_build_job(job, status="cancelled", returncode=None)
                return
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            list(job.get("argv") or []),
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with _MAP_PACK_BUILD_JOB_LOCK:
            job["process"] = process
            if bool(job.get("cancel_requested")):
                try:
                    process.terminate()
                except Exception:
                    pass
        assert process.stdout is not None
        for raw_line in process.stdout:
            with _MAP_PACK_BUILD_JOB_LOCK:
                _append_build_job_line(job, raw_line)
        returncode = process.wait()
        with _MAP_PACK_BUILD_JOB_LOCK:
            cancelled = bool(job.get("cancel_requested"))
        if cancelled:
            _finish_build_job(job, status="cancelled", returncode=returncode)
        elif returncode == 0:
            _finish_build_job(job, status="succeeded", returncode=returncode)
        else:
            _finish_build_job(job, status="failed", returncode=returncode)
    except Exception as exc:
        with _MAP_PACK_BUILD_JOB_LOCK:
            job["error"] = str(exc or "map pack build failed")
            _append_build_job_line(job, f"[map-pack] error: {job['error']}")
            job["status"] = "failed"
            job["finished_at"] = time.time()
            job["returncode"] = None
    finally:
        with _MAP_PACK_BUILD_JOB_LOCK:
            job["process"] = None


def start_map_pack_build_job(request_raw: object) -> dict[str, Any]:
    global _MAP_PACK_BUILD_JOB
    try:
        argv, detail = _map_pack_build_argv(request_raw)
    except ValueError as exc:
        payload = _map_pack_error(str(exc))
        payload["http_status"] = 400
        return payload

    with _MAP_PACK_BUILD_JOB_LOCK:
        if (
            _MAP_PACK_BUILD_JOB
            and str(_MAP_PACK_BUILD_JOB.get("status") or "") == "running"
        ):
            payload = _map_pack_error(
                "a map pack build is already running",
                code="build_already_running",
            )
            payload["http_status"] = 409
            return payload
        now = time.time()
        job = {
            "id": f"map-pack-{int(now * 1000)}",
            "status": "running",
            "pack_id": detail.get("pack_id"),
            "started_at": now,
            "finished_at": 0.0,
            "returncode": None,
            "lines": [
                "[map-pack] please wait: building map pack. "
                "Downloads may take a while."
            ],
            "detail": detail,
            "argv": argv,
            "process": None,
            "cancel_requested": False,
        }
        _MAP_PACK_BUILD_JOB = job
        thread = threading.Thread(
            target=_run_build_job,
            args=(job,),
            name="meshdash-map-pack-build",
            daemon=True,
        )
        job["thread"] = thread
        thread.start()
        return _build_job_payload(job)


def map_pack_build_status_payload() -> dict[str, Any]:
    with _MAP_PACK_BUILD_JOB_LOCK:
        return _build_job_payload(_MAP_PACK_BUILD_JOB)


def cancel_map_pack_build_job() -> dict[str, Any]:
    with _MAP_PACK_BUILD_JOB_LOCK:
        job = _MAP_PACK_BUILD_JOB
        if not job or str(job.get("status") or "") != "running":
            return {"ok": True, "cancelled": False, "active": False}
        job["cancel_requested"] = True
        process = job.get("process")
        _append_build_job_line(job, "[map-pack] cancellation requested")

    if isinstance(process, subprocess.Popen):
        try:
            process.terminate()
            try:
                process.wait(timeout=_BUILD_JOB_TERMINATE_GRACE_SEC)
            except subprocess.TimeoutExpired:
                process.kill()
        except Exception:
            pass
    return {"ok": True, "cancelled": True, "active": True}


def install_built_map_pack(request_raw: object) -> dict[str, Any]:
    request = request_raw if isinstance(request_raw, Mapping) else {}
    try:
        pack_id = _map_pack_build_pack_id(request)
    except ValueError as exc:
        payload = _map_pack_error(str(exc))
        payload["http_status"] = 400
        return payload
    zip_path = Path.cwd() / f"{pack_id}.zip"
    if not zip_path.is_file():
        payload = _map_pack_error(
            f"zip not found: {zip_path.name}; run mappacks build first",
            code="zip_not_found",
        )
        payload["http_status"] = 404
        return payload
    error = install_pack_zip(pack_id, zip_path)
    if error:
        payload = _map_pack_error(error, code="install_failed")
        payload["http_status"] = 400
        return payload
    manifest = load_installed_manifest(pack_id) or {}
    return {
        "ok": True,
        "installed": True,
        "pack_id": pack_id,
        "zip": zip_path.name,
        "installed_pack": _installed_pack_summary(manifest),
    }


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
            block = handle.read(min(_ZIP_READ_CHUNK_BYTES, max(1, limit - total + 1)))
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
    pack_ids: list[str] = []
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
            "label": str((manifest or {}).get("label") or pack_id),
            "description": str((manifest or {}).get("description") or ""),
            "state": state,
            "installed": manifest is not None,
            "sideload_ready": sideload_ready,
            "install_command": _installer_command(pack_id),
        }
        if manifest is not None:
            entry["installed_pack"] = _installed_pack_summary(manifest)
        packs.append(entry)

    return {
        "ok": True,
        "packs": packs,
        "packs_dir": str(packs_dir),
        "packs_dir_resolved": str(packs_dir.resolve()),
        "packs_dir_command": _packs_dir_command_path(),
        "packs_dir_command_arg": _packs_dir_command_arg(),
        "install_command_prefix": _installer_command_prefix(),
        "build_command_prefix": _build_command_prefix(),
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
