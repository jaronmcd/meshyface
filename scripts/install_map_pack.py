#!/usr/bin/env python3
"""Install, list, or remove local map expansion packs.

The dashboard web UI is read-only for map packs; this script is the
install path. Run it on the machine that hosts the dashboard so the
pack lands in that machine's map packs folder (map_packs/ relative to
the dashboard's working directory unless --packs-dir or the
MESH_DASHBOARD_MAP_PACKS_DIR environment variable says otherwise).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meshdash import map_packs  # noqa: E402

_FILE_CHUNK_BYTES = 256 * 1024


def _human_bytes(count: object) -> str:
    try:
        value = float(count)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_FILE_CHUNK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _zip_manifest_preview(zip_path: Path) -> dict[str, object]:
    """Best-effort read of the pack manifest inside a zip for size preview."""
    try:
        with zipfile.ZipFile(zip_path) as archive:
            raw = map_packs._read_zip_member_limited(
                archive, "manifest.json", map_packs._MAX_MANIFEST_BYTES
            )
        manifest = json.loads(raw.decode("utf-8"))
        return manifest if isinstance(manifest, dict) else {}
    except Exception:
        return {}


def _pack_id_from_zip(zip_path: Path) -> str:
    manifest = _zip_manifest_preview(zip_path)
    return map_packs._clean_pack_id(manifest.get("id"))


def _confirm_install(
    pack_id: str, zip_path: Path, packs_dir: Path, assume_yes: bool
) -> bool:
    manifest = _zip_manifest_preview(zip_path)
    total_bytes = 0
    try:
        total_bytes = max(0, int(manifest.get("total_bytes") or 0))
    except (TypeError, ValueError):
        total_bytes = 0
    layers = manifest.get("layers")
    layer_names = sorted(layers.keys()) if isinstance(layers, dict) else []
    if total_bytes:
        print(
            f"[map-pack] {pack_id}: installs {_human_bytes(total_bytes)} across "
            f"{len(layer_names)} layers ({', '.join(layer_names)})"
        )
    try:
        free_bytes = shutil.disk_usage(packs_dir).free
        print(f"[map-pack] free space in {packs_dir}: {_human_bytes(free_bytes)}")
        if total_bytes and free_bytes < total_bytes + (32 * 1024 * 1024):
            print(
                f"not enough free space: pack needs {_human_bytes(total_bytes)} "
                f"plus working room",
                file=sys.stderr,
            )
            return False
    except OSError:
        pass
    if assume_yes or not sys.stdin.isatty():
        return True
    answer = input("Continue? [Y/n] ").strip().lower()
    return answer in ("", "y", "yes")


def _print_status() -> None:
    payload = map_packs.map_pack_status_payload()
    print(f"[map-pack] packs dir: {payload.get('packs_dir')}")
    for pack in payload.get("packs", []):
        line = f"  {pack.get('id')}: {pack.get('state')}"
        installed = pack.get("installed_pack") or {}
        if installed:
            size = _human_bytes(installed.get("total_bytes"))
            layer_count = len(installed.get("layers") or [])
            line += f" ({size} on disk, {layer_count} layers)"
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install, list, or remove offline map expansion packs."
    )
    parser.add_argument(
        "pack_id",
        nargs="?",
        default="",
        help="Pack id to install/remove; inferred from --zip manifest when omitted.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--zip",
        type=Path,
        default=None,
        help="Install from a local map pack zip.",
    )
    parser.add_argument(
        "--sha256",
        default="",
        help="Expected sha256 of the pack zip; installation aborts on mismatch.",
    )
    parser.add_argument(
        "--packs-dir",
        type=Path,
        default=None,
        help="Map packs directory (default: map_packs/ under the current directory).",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Remove the installed pack (and any staged zip) instead of installing.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show pack status and exit.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the size confirmation prompt.",
    )
    args = parser.parse_args()

    if args.packs_dir is not None:
        os.environ["MESH_DASHBOARD_MAP_PACKS_DIR"] = str(args.packs_dir.resolve())

    if args.list:
        _print_status()
        return 0

    if args.download:
        print(
            "install_map_pack.py installs local map pack zips; it does not "
            "download first-party expansion packs. Build a zip with "
            "scripts/build_map_pack.py --download, then install it with "
            "scripts/install_map_pack.py --zip <pack.zip>.",
            file=sys.stderr,
        )
        return 2

    zip_pack_id = ""
    if args.zip is not None:
        if not args.zip.is_file():
            print(f"zip not found: {args.zip}", file=sys.stderr)
            return 1
        zip_pack_id = _pack_id_from_zip(args.zip)

    pack_id = map_packs._clean_pack_id(args.pack_id) or zip_pack_id
    if not pack_id:
        print(
            "pack id is required unless --zip points to a valid map pack "
            "with an id in manifest.json",
            file=sys.stderr,
        )
        return 2

    packs_dir = map_packs.map_packs_dir()

    if args.delete:
        removed_any = False
        error = map_packs.remove_installed_pack(pack_id)
        if not error:
            print(f"[map-pack] removed installed pack {pack_id}")
            removed_any = True
        elif error != "pack is not installed":
            print(f"delete failed: {error}", file=sys.stderr)
            return 1
        staged_zip = packs_dir / f"{pack_id}.zip"
        if staged_zip.exists():
            staged_zip.unlink()
            print(f"[map-pack] removed staged zip {staged_zip}")
            removed_any = True
        if not removed_any:
            print(f"[map-pack] nothing to remove for {pack_id}")
        return 0

    packs_dir.mkdir(parents=True, exist_ok=True)
    staged_zip = packs_dir / f"{pack_id}.zip"
    cleanup_zip_after_install = False

    if args.zip is not None:
        source_zip = args.zip
    elif staged_zip.is_file() and staged_zip.stat().st_size > 0:
        print(f"[map-pack] using staged zip {staged_zip}")
        source_zip = staged_zip
        cleanup_zip_after_install = True
    else:
        print(
            f"no pack zip found for {pack_id}.\n"
            f"Place the zip at {staged_zip}, or point --zip at a local file.",
            file=sys.stderr,
        )
        return 2

    if args.sha256:
        actual = _sha256_of_file(source_zip)
        if actual.lower() != args.sha256.strip().lower():
            print(
                f"sha256 mismatch: expected {args.sha256}, got {actual}",
                file=sys.stderr,
            )
            return 1
        print("[map-pack] sha256 verified")

    if not _confirm_install(pack_id, source_zip, packs_dir, args.yes):
        print("[map-pack] install cancelled")
        return 1

    print(f"[map-pack] installing {pack_id} from {source_zip}")
    error = map_packs.install_pack_zip(pack_id, source_zip)
    if error:
        print(f"install failed: {error}", file=sys.stderr)
        return 1
    if cleanup_zip_after_install:
        try:
            source_zip.unlink()
        except OSError:
            pass

    manifest = map_packs.load_installed_manifest(pack_id) or {}
    total = _human_bytes(manifest.get("total_bytes"))
    layers = manifest.get("layers")
    layer_count = len(layers) if isinstance(layers, dict) else 0
    print(f"[map-pack] installed {pack_id}: {total} on disk, {layer_count} layers")
    print("[map-pack] open the dashboard Settings -> Maps tab to confirm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
