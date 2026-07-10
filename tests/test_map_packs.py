from __future__ import annotations

import hashlib
import json
import shlex
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from meshdash import map_packs  # noqa: E402
from meshdash.html_js import build_dashboard_js  # noqa: E402


def _chunk_payload() -> bytes:
    collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Testville", "scalerank": 3, "population": 1200},
                "geometry": {"type": "Point", "coordinates": [-120.5, 45.5]},
            }
        ],
    }
    return json.dumps(collection, separators=(",", ":")).encode("utf-8")


def _build_pack_zip(
    zip_path: Path,
    *,
    pack_id: str = "global_detail",
    chunk_sha: str | None = None,
    pack_format: str = map_packs.PACK_FORMAT,
    declared_chunk_bytes: int | None = None,
    declared_total_bytes: int | None = None,
) -> None:
    chunk = _chunk_payload()
    chunk_bytes = len(chunk) if declared_chunk_bytes is None else declared_chunk_bytes
    manifest = {
        "format": pack_format,
        "id": pack_id,
        "version": 1,
        "label": "Test Pack",
        "attribution": "test",
        "cell_deg": 15,
        "layers": {
            "cities": {
                "kind": "point",
                "min_zoom": 4,
                "chunks": {
                    "c3r9": {
                        "path": "chunks/cities/c3r9.json",
                        "bytes": chunk_bytes,
                        "sha256": chunk_sha
                        if chunk_sha is not None
                        else hashlib.sha256(chunk).hexdigest(),
                        "features": 1,
                    }
                },
            }
        },
        "counts": {"cities": 1},
        "total_bytes": len(chunk) if declared_total_bytes is None else declared_total_bytes,
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
        archive.writestr("chunks/cities/c3r9.json", chunk)


@pytest.fixture
def packs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "map_packs"
    target.mkdir()
    monkeypatch.setenv("MESH_DASHBOARD_MAP_PACKS_DIR", str(target))
    return target


def test_install_pack_zip_and_read_chunk(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert error == ""
    manifest = map_packs.load_installed_manifest("global_detail")
    assert manifest is not None
    assert manifest["id"] == "global_detail"
    chunk = map_packs.read_map_pack_chunk("global_detail", "chunks/cities/c3r9.json")
    assert chunk == _chunk_payload()


def test_install_pack_zip_rejects_bad_checksum(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path, chunk_sha="0" * 64)

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "checksum" in error
    assert map_packs.load_installed_manifest("global_detail") is None
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_chunk_byte_mismatch_and_cleans_staging(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path, declared_chunk_bytes=len(_chunk_payload()) + 1)

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "byte count" in error
    assert map_packs.load_installed_manifest("global_detail") is None
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_total_byte_mismatch_and_cleans_staging(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path, declared_total_bytes=len(_chunk_payload()) + 1)

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "installed byte count" in error
    assert map_packs.load_installed_manifest("global_detail") is None
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_declared_chunk_over_size_limit(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(
        zip_path,
        declared_chunk_bytes=map_packs._MAX_INSTALLED_PACK_BYTES + 1,
        declared_total_bytes=len(_chunk_payload()),
    )

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "exceeds size limit" in error
    assert map_packs.load_installed_manifest("global_detail") is None
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_unknown_format(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path, pack_format="meshdash-map-pack/999")

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "format" in error


def test_install_pack_zip_rejects_mismatched_id(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path, pack_id="other_pack")

    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert "does not match" in error


def test_install_pack_zip_rejects_invalid_pack_id(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)

    error = map_packs.install_pack_zip("../evil", zip_path)

    assert error == "invalid pack id"
    assert map_packs.load_installed_manifest("global_detail") is None


def test_read_chunk_rejects_traversal_and_unknown_paths(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    assert map_packs.read_map_pack_chunk("global_detail", "../manifest.json") is None
    assert map_packs.read_map_pack_chunk("global_detail", "chunks/../../manifest.json") is None
    assert map_packs.read_map_pack_chunk("global_detail", "manifest.json") is None
    assert map_packs.read_map_pack_chunk("global_detail", "chunks/cities/missing.json") is None
    assert map_packs.read_map_pack_chunk("../etc", "chunks/cities/c3r9.json") is None


def test_status_payload_tracks_only_local_sideload_and_installed(packs_dir: Path) -> None:
    payload = map_packs.map_pack_status_payload()
    assert payload["ok"] is True
    assert payload["packs"] == []
    assert "install_map_pack.py" in payload["install_command_prefix"]
    assert "build_map_pack.py" in payload["build_command_prefix"]
    assert not Path(shlex.split(payload["install_command_prefix"])[0]).is_absolute()
    assert not Path(shlex.split(payload["install_command_prefix"])[1]).is_absolute()
    assert payload["packs_dir_resolved"] == str(packs_dir.resolve())
    assert payload["packs_dir_command"] == str(packs_dir)

    zip_path = packs_dir / "mymesh.zip"
    _build_pack_zip(zip_path, pack_id="mymesh")
    payload = map_packs.map_pack_status_payload()
    entries = {pack["id"]: pack for pack in payload["packs"]}
    states = {pack_id: pack["state"] for pack_id, pack in entries.items()}
    assert states == {"mymesh": "sideload_ready"}
    assert "--download" not in entries["mymesh"]["install_command"]
    assert "install_map_pack.py" in entries["mymesh"]["install_command"]
    assert "--packs-dir" in entries["mymesh"]["install_command"]
    assert entries["mymesh"]["install_command"].startswith(
        payload["install_command_prefix"]
    )

    assert map_packs.install_pack_zip("mymesh", zip_path) == ""
    zip_path.unlink()
    payload = map_packs.map_pack_status_payload()
    entry = next(p for p in payload["packs"] if p["id"] == "mymesh")
    assert entry["state"] == "installed"
    assert entry["installed"] is True
    assert entry["installed_pack"]["version"] == 1
    assert entry["installed_pack"]["chunk_count"] == 1


def test_status_payload_install_command_uses_portable_default_packs_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MESH_DASHBOARD_MAP_PACKS_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    packs_dir = tmp_path / "map_packs"
    packs_dir.mkdir()
    _build_pack_zip(packs_dir / "mymesh.zip", pack_id="mymesh")

    payload = map_packs.map_pack_status_payload()
    entry = next(p for p in payload["packs"] if p["id"] == "mymesh")
    command = shlex.split(entry["install_command"])
    packs_dir = command[command.index("--packs-dir") + 1]

    assert packs_dir == "map_packs"
    assert not Path(packs_dir).is_absolute()
    assert payload["packs_dir_command"] == "map_packs"
    assert payload["packs_dir_command_arg"] == "map_packs"
    assert payload["packs_dir_resolved"] == str((tmp_path / "map_packs").resolve())


def test_remove_installed_pack(packs_dir: Path) -> None:
    assert map_packs.remove_installed_pack("global_detail") == "pack is not installed"
    assert map_packs.remove_installed_pack("../evil") == "invalid pack id"

    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    assert map_packs.remove_installed_pack("global_detail") == ""
    assert map_packs.load_installed_manifest("global_detail") is None


def _run_installer_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    import install_map_pack

    monkeypatch.setattr(sys, "argv", ["install_map_pack.py", *argv])
    return install_map_pack.main()


def _run_build_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    import build_map_pack

    monkeypatch.setattr(sys, "argv", ["build_map_pack.py", *argv])
    return build_map_pack.main()


def test_installer_cli_installs_staged_zip(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)

    assert _run_installer_cli(monkeypatch, "global_detail") == 0
    assert map_packs.load_installed_manifest("global_detail") is not None
    assert not zip_path.exists()


def test_installer_cli_installs_external_zip_and_keeps_it(
    packs_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = tmp_path / "elsewhere.zip"
    _build_pack_zip(zip_path, pack_id="mymesh")

    assert _run_installer_cli(monkeypatch, "--zip", str(zip_path)) == 0
    assert map_packs.load_installed_manifest("mymesh") is not None
    assert zip_path.exists()


def test_installer_cli_rejects_sha256_mismatch(
    packs_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = tmp_path / "pack.zip"
    _build_pack_zip(zip_path)

    result = _run_installer_cli(
        monkeypatch, "global_detail", "--zip", str(zip_path), "--sha256", "0" * 64
    )
    assert result == 1
    assert map_packs.load_installed_manifest("global_detail") is None


def test_installer_cli_requires_pack_id_or_zip_manifest(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_installer_cli(monkeypatch) == 2

    err = capsys.readouterr().err
    assert "pack id is required unless --zip points to a valid map pack" in err


def test_installer_cli_frames_download_as_build_step(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_installer_cli(monkeypatch, "global_detail", "--download") == 2

    err = capsys.readouterr().err
    assert "install_map_pack.py installs local map pack zips" in err
    assert "scripts/build_map_pack.py --download" in err


def test_installer_cli_delete(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    assert _run_installer_cli(monkeypatch, "global_detail", "--delete") == 0
    assert map_packs.load_installed_manifest("global_detail") is None
    assert not zip_path.exists()


def test_build_script_line_clipping_splits_cells() -> None:
    import build_map_pack

    feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "LineString",
            "coordinates": [[-10.0, 5.0], [10.0, 5.0]],
        },
    }
    chunks = build_map_pack._chunk_line_features([feature])

    # The line crosses the meridian cell boundary at lon 0 inside row 6.
    assert set(chunks.keys()) == {"c11r6", "c12r6"}
    for features in chunks.values():
        assert len(features) == 1
        coords = features[0]["geometry"]["coordinates"]
        lons = [point[0] for point in coords]
        assert max(lons) - min(lons) <= 15.0 + (2 * build_map_pack.CLIP_MARGIN_DEG)


def test_build_script_center_assignment_keeps_feature_once() -> None:
    import build_map_pack

    feature = {
        "type": "Feature",
        "properties": {"name": "Big Lake"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[1.0, 1.0], [9.0, 1.0], [9.0, 9.0], [1.0, 9.0], [1.0, 1.0]]],
        },
    }
    chunks = build_map_pack._chunk_center_features([feature])

    assert list(chunks.keys()) == ["c12r6"]
    assert len(chunks["c12r6"]) == 1


def _write_region_sources(source_dir: Path) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "countryInfo.txt").write_text(
        "# comment line\n"
        "US\tUSA\t840\tUS\tUnited States\tWashington\n"
        "NL\tNLD\t528\tNL\tThe Netherlands\tAmsterdam\n",
        encoding="utf-8",
    )
    (source_dir / "admin1CodesASCII.txt").write_text(
        "US.MN\tMinnesota\tMinnesota\t5037779\n"
        "US.KS\tKansas\tKansas\t4273857\n",
        encoding="utf-8",
    )
    rows = [
        # id name ascii alt lat lon fclass fcode cc cc2 admin1 admin2 admin3 admin4 pop
        "1\tEagan\tEagan\t\t44.8\t-93.16\tP\tPPL\tUS\t\tMN\t\t\t\t66286",
        "2\tDuluth\tDuluth\t\t46.78\t-92.1\tP\tPPL\tUS\t\tMN\t\t\t\t86697",
        "3\tWichita\tWichita\t\t37.69\t-97.34\tP\tPPL\tUS\t\tKS\t\t\t\t397532",
        "4\tAmsterdam\tAmsterdam\t\t52.37\t4.89\tP\tPPLC\tNL\t\tNH\t\t\t\t741636",
    ]
    with zipfile.ZipFile(source_dir / "cities500.zip", "w") as archive:
        archive.writestr("cities500.txt", "\n".join(rows) + "\n")


def test_build_script_resolves_regions(tmp_path: Path) -> None:
    import build_map_pack

    source_dir = tmp_path / "sources"
    _write_region_sources(source_dir)

    slug, label, bbox = build_map_pack.resolve_region(source_dir, "Minnesota")
    assert slug == "region_us_mn"
    assert label == "Minnesota, United States"
    assert bbox[0] < -93.16 < bbox[2]
    assert bbox[1] < 44.8 and bbox[3] > 46.78

    slug, label, _bbox = build_map_pack.resolve_region(source_dir, "US.MN")
    assert slug == "region_us_mn"

    slug, label, _bbox = build_map_pack.resolve_region(source_dir, "Netherlands")
    assert slug == "region_nl"
    assert label == "The Netherlands"

    slug, label, bbox = build_map_pack.resolve_region(source_dir, "eagan")
    assert slug == "region_eagan"
    assert label == "Eagan, Minnesota"
    assert bbox[2] - bbox[0] == pytest.approx(5.0)

    with pytest.raises(ValueError, match="no country"):
        build_map_pack.resolve_region(source_dir, "Atlantis")


def test_build_script_cells_for_bbox() -> None:
    import build_map_pack

    # Minnesota-ish bbox spans two columns and two rows of the 15-degree grid.
    cells = build_map_pack.cells_for_bbox((-98.0, 42.5, -89.3, 49.9))
    assert cells == {"c5r8", "c5r9", "c6r8", "c6r9"}

    # A bbox inside one cell yields exactly that cell.
    assert build_map_pack.cells_for_bbox((1.0, 1.0, 2.0, 2.0)) == {"c12r6"}


def test_build_script_layer_selection() -> None:
    import build_map_pack

    assert build_map_pack.parse_layer_selection("", "") is None
    assert build_map_pack.parse_layer_selection("cities,roads", "") == {"cities", "roads"}
    excluded = build_map_pack.parse_layer_selection("", "railroads")
    assert excluded is not None
    assert "railroads" not in excluded and "cities" in excluded

    with pytest.raises(ValueError, match="not both"):
        build_map_pack.parse_layer_selection("cities", "roads")
    with pytest.raises(ValueError, match="unknown layers"):
        build_map_pack.parse_layer_selection("citiez", "")
    with pytest.raises(ValueError, match="exclude every layer"):
        build_map_pack.parse_layer_selection(
            "", ",".join(build_map_pack.LAYER_SPECS)
        )

    assert build_map_pack.parse_country_codes("") == []
    assert build_map_pack.parse_country_codes("us, CA,us") == ["US", "CA"]
    with pytest.raises(ValueError, match="ISO-2"):
        build_map_pack.parse_country_codes("USA")


def test_build_script_center_radius_bbox() -> None:
    import build_map_pack

    lat, lon = build_map_pack.parse_center("44.8,-93.2")
    assert (lat, lon) == (44.8, -93.2)
    with pytest.raises(ValueError):
        build_map_pack.parse_center("44.8")
    with pytest.raises(ValueError):
        build_map_pack.parse_center("95.0,-93.2")

    west, south, east, north = build_map_pack.bbox_for_center_radius(44.8, -93.2, 100.0)
    assert south < 44.8 < north
    assert west < -93.2 < east
    assert north - south == pytest.approx(2 * 100.0 / 111.32, rel=0.01)
    # Longitude span must widen with latitude.
    assert (east - west) > (north - south)


def test_build_script_center_region_prefers_biggest_nearby_city(tmp_path: Path) -> None:
    import build_map_pack

    source_dir = tmp_path / "sources"
    _write_region_sources(source_dir)

    slug, label, _bbox = build_map_pack.resolve_center_region(
        source_dir, 44.8, -93.16, 50.0
    )
    assert slug == "region_eagan_50km"
    assert label == "Eagan area (50 km)"

    with pytest.raises(ValueError, match="radius"):
        build_map_pack.resolve_center_region(source_dir, 44.8, -93.16, 0.0)


def test_build_script_history_center_trims_outliers(tmp_path: Path) -> None:
    import sqlite3

    import build_map_pack

    db_path = tmp_path / "history.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE node_positions ("
        "id INTEGER PRIMARY KEY, created_unix INTEGER, node_id TEXT, "
        "lat REAL, lon REAL, altitude REAL, sats_in_view INTEGER)"
    )
    rows = []
    for index in range(10):
        rows.append((1000 + index, f"node{index}", 45.0 + index * 0.01, -93.0))
    rows.append((2000, "faraway1", 44.0, -121.8))
    rows.append((2001, "faraway2", 37.2, -121.9))
    connection.executemany(
        "INSERT INTO node_positions (created_unix, node_id, lat, lon) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()

    lat, lon, radius_km, node_count, covered = build_map_pack.resolve_history_center(
        db_path
    )
    assert node_count == 12
    assert 44.9 < lat < 45.2 and -93.1 < lon < -92.9
    assert radius_km < 300.0
    assert covered == 10

    with pytest.raises(ValueError, match="not found"):
        build_map_pack.resolve_history_center(tmp_path / "missing.sqlite3")


def test_build_script_peaks_loader_and_country_resolution(tmp_path: Path) -> None:
    import build_map_pack

    source_dir = tmp_path / "sources"
    _write_region_sources(source_dir)

    # Minnesota-ish bbox only contains US cities from the fixture.
    assert build_map_pack.country_codes_for_bbox(
        source_dir, (-98.0, 42.5, -89.3, 49.9)
    ) == ["US"]
    assert build_map_pack.country_codes_for_bbox(
        source_dir, (4.0, 52.0, 5.5, 53.0)
    ) == ["NL"]

    rows = [
        # id name ascii alt lat lon fclass fcode cc cc2 a1 a2 a3 a4 pop elev dem tz mod
        "1\tEagle Mountain\tEagle Mountain\t\t47.897\t-90.560\tT\tPK\tUS\t\tMN"
        "\t\t\t\t0\t701\t694\tUS/Central\t2020-01-01",
        "2\tBlack Elk Peak\tBlack Elk Peak\t\t43.866\t-103.531\tT\tPK\tUS\t\tSD"
        "\t\t\t\t0\t\t2207\tUS/Mountain\t2020-01-01",
        "3\tSome Town\tSome Town\t\t45.0\t-93.0\tP\tPPL\tUS\t\tMN"
        "\t\t\t\t500\t\t260\tUS/Central\t2020-01-01",
        "4\tNameless Ridge\tNameless Ridge\t\t44.0\t-93.5\tT\tRDGE\tUS\t\tMN"
        "\t\t\t\t0\t300\t300\tUS/Central\t2020-01-01",
    ]
    with zipfile.ZipFile(source_dir / "geonames_US.zip", "w") as archive:
        archive.writestr("US.txt", "\n".join(rows) + "\n")

    features = build_map_pack._load_peaks_features(source_dir, ["US"])
    by_name = {f["properties"]["name"]: f["properties"] for f in features}
    assert set(by_name) == {"Eagle Mountain", "Black Elk Peak"}
    assert by_name["Eagle Mountain"]["elevation"] == 701
    # Elevation column empty falls back to the dem column.
    assert by_name["Black Elk Peak"]["elevation"] == 2207


def test_build_script_peaks_country_resolution_requires_explicit_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "sources"
    _write_region_sources(source_dir)

    result = _run_build_cli(
        monkeypatch,
        "--source-dir",
        str(source_dir),
        "--center",
        "0,0",
        "--radius-km",
        "10",
        "--estimate",
    )
    captured = capsys.readouterr()
    assert result == 2
    assert "--peaks-countries" in captured.err

    result = _run_build_cli(
        monkeypatch,
        "--source-dir",
        str(source_dir),
        "--center",
        "0,0",
        "--radius-km",
        "10",
        "--peaks-countries",
        "US",
        "--estimate",
    )
    captured = capsys.readouterr()
    assert result == 0
    assert "peaks countries: US" in captured.out


def test_build_script_history_radius_override_reports_matching_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sqlite3

    source_dir = tmp_path / "sources"
    _write_region_sources(source_dir)
    db_path = tmp_path / "history.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE node_positions ("
        "id INTEGER PRIMARY KEY, created_unix INTEGER, node_id TEXT, "
        "lat REAL, lon REAL, altitude REAL, sats_in_view INTEGER)"
    )
    rows = [
        (1000 + index, f"node{index}", 45.0 + index * 0.01, -93.0)
        for index in range(5)
    ]
    connection.executemany(
        "INSERT INTO node_positions (created_unix, node_id, lat, lon) "
        "VALUES (?, ?, ?, ?)",
        rows,
    )
    connection.commit()
    connection.close()

    result = _run_build_cli(
        monkeypatch,
        "--source-dir",
        str(source_dir),
        "--from-history",
        "--history-db",
        str(db_path),
        "--radius-km",
        "1",
        "--exclude-layers",
        "peaks",
        "--estimate",
    )
    captured = capsys.readouterr()
    assert result == 0
    assert "radius 1 km covers 1 nodes" in captured.out


def test_build_script_estimate_math() -> None:
    import build_map_pack

    cells = {"c5r8", "c5r9"}
    estimates = build_map_pack.estimate_pack_bytes({"cities", "roads"}, cells)
    assert set(estimates) == {"cities", "roads"}
    for layer_name, layer_bytes in estimates.items():
        avg, _count = build_map_pack._ESTIMATE_LAYER_STATS[layer_name]
        assert layer_bytes == avg * 2

    global_estimates = build_map_pack.estimate_pack_bytes(None, None)
    assert set(global_estimates) == set(build_map_pack.LAYER_SPECS)


def test_installer_cli_confirmation_can_cancel(
    packs_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = tmp_path / "pack.zip"
    _build_pack_zip(zip_path)

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    result = _run_installer_cli(monkeypatch, "global_detail", "--zip", str(zip_path))
    assert result == 1
    assert map_packs.load_installed_manifest("global_detail") is None

    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    assert _run_installer_cli(monkeypatch, "global_detail", "--zip", str(zip_path)) == 0
    assert map_packs.load_installed_manifest("global_detail") is not None


def test_build_pack_cleans_stale_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import build_map_pack

    output_dir = tmp_path / "pack"
    stale_chunk = output_dir / "chunks" / "cities" / "c99r99.json"
    stale_chunk.parent.mkdir(parents=True)
    stale_chunk.write_text("stale", encoding="utf-8")

    feature = {
        "type": "Feature",
        "properties": {"name": "Fresh"},
        "geometry": {"type": "Point", "coordinates": [1.0, 1.0]},
    }
    monkeypatch.setattr(
        build_map_pack,
        "build_layer_features",
        lambda _source_dir, _layer_names=None, **_kwargs: {"cities": [feature]},
    )

    manifest = build_map_pack.build_pack(tmp_path / "sources", output_dir, 1)

    assert not stale_chunk.exists()
    assert "c12r6" in manifest["layers"]["cities"]["chunks"]


def test_status_payload_uses_manifest_description_for_custom_packs(packs_dir: Path) -> None:
    zip_path = packs_dir / "region_test.zip"
    manifest_extra = {"description": "Regional test coverage."}
    chunk = _chunk_payload()
    manifest = {
        "format": map_packs.PACK_FORMAT,
        "id": "region_test",
        "version": 1,
        "label": "Region Test",
        "attribution": "test",
        "cell_deg": 15,
        "layers": {
            "cities": {
                "kind": "point",
                "min_zoom": 4,
                "chunks": {
                    "c3r9": {
                        "path": "chunks/cities/c3r9.json",
                        "bytes": len(chunk),
                        "sha256": hashlib.sha256(chunk).hexdigest(),
                        "features": 1,
                    }
                },
            }
        },
        "counts": {"cities": 1},
        "total_bytes": len(chunk),
        **manifest_extra,
    }
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
        archive.writestr("chunks/cities/c3r9.json", chunk)

    assert map_packs.install_pack_zip("region_test", zip_path) == ""
    entry = next(
        p for p in map_packs.map_pack_status_payload()["packs"]
        if p["id"] == "region_test"
    )
    assert entry["state"] == "installed"
    assert entry["label"] == "Region Test"
    assert entry["description"] == "Regional test coverage."


def _manifest_for_chunk(
    chunk: bytes,
    *,
    pack_id: str = "global_detail",
    **overrides: object,
) -> dict:
    manifest = {
        "format": map_packs.PACK_FORMAT,
        "id": pack_id,
        "version": 1,
        "label": "Test Pack",
        "attribution": "test",
        "cell_deg": 15,
        "layers": {
            "cities": {
                "kind": "point",
                "min_zoom": 4,
                "chunks": {
                    "c3r9": {
                        "path": "chunks/cities/c3r9.json",
                        "bytes": len(chunk),
                        "sha256": hashlib.sha256(chunk).hexdigest(),
                        "features": 1,
                    }
                },
            }
        },
        "counts": {"cities": 1},
        "total_bytes": len(chunk),
    }
    manifest.update(overrides)
    return manifest


def _write_zip(zip_path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_dashboard_js_renders_mesh_sized_map_pack_commands() -> None:
    js = build_dashboard_js(
        refresh_ms=1000,
        node_history_hours=24,
        node_history_max_points=240,
    )

    assert "function settingsMapsMeshSummary(state = latestState)" in js
    assert 'const host = document.getElementById("settings-maps-build-command");' in js
    assert "Mesh-sized map pack" in js
    assert "nodes with GPS. Center" in js
    assert (
        "buildCommand = `${buildPrefix} --source-dir map_sources --download "
        "--center ${mesh.center} --radius-km ${radius}${layersArg} "
        "--pack-id mymesh --zip mymesh.zip`;"
    ) in js
    assert (
        "buildCommand = `${buildPrefix} --source-dir map_sources --download "
        "--from-history${layersArg} --pack-id mymesh --zip mymesh.zip`;"
    ) in js
    assert "const installCommand = `${installPrefix} --zip mymesh.zip${packsDir}`;" in js
    assert "appendSettingsMapsCommandRow(card, \"Build\", buildCommand);" in js
    assert "appendSettingsMapsCommandRow(card, \"Install\", installCommand);" in js


def test_validate_manifest_obj_reports_each_defect() -> None:
    validate = map_packs._validate_manifest_obj
    chunk = _chunk_payload()

    assert validate(["not", "a", "dict"]) == "manifest is not an object"
    assert "unsupported pack format" in validate({"format": "other/1"})
    assert "no valid pack id" in validate(
        {"format": map_packs.PACK_FORMAT, "id": "Bad Id!"}
    )
    assert "does not match expected" in validate(
        _manifest_for_chunk(chunk, pack_id="other_pack"), "global_detail"
    )
    assert "has no layers" in validate(_manifest_for_chunk(chunk, layers={}))
    assert "has no layers" in validate(_manifest_for_chunk(chunk, layers="nope"))
    assert "is not an object" in validate(
        _manifest_for_chunk(chunk, layers={"cities": "nope"})
    )
    assert "has no chunks object" in validate(
        _manifest_for_chunk(chunk, layers={"cities": {"kind": "point"}})
    )
    assert "is not an object" in validate(
        _manifest_for_chunk(chunk, layers={"cities": {"chunks": {"c3r9": "nope"}}})
    )
    assert "unsafe path" in validate(
        _manifest_for_chunk(
            chunk,
            layers={"cities": {"chunks": {"c3r9": {"path": "../../etc/passwd"}}}},
        )
    )


def test_load_installed_manifest_rejects_bad_id_and_invalid_manifest(
    packs_dir: Path,
) -> None:
    assert map_packs.load_installed_manifest("Bad Id!") is None

    install_dir = packs_dir / "global_detail"
    install_dir.mkdir()
    (install_dir / "manifest.json").write_text(
        json.dumps({"format": "other/1", "id": "global_detail"}), encoding="utf-8"
    )
    assert map_packs.load_installed_manifest("global_detail") is None


def test_fail_install_swallows_cleanup_errors(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staging = packs_dir / ".install-x.tmp"
    staging.mkdir()

    def _broken_rmtree(path: object, **kwargs: object) -> None:
        raise OSError("cleanup blocked")

    monkeypatch.setattr(map_packs.shutil, "rmtree", _broken_rmtree)
    assert map_packs._fail_install(staging, "original error") == "original error"


def test_install_pack_zip_rejects_missing_or_unreadable_manifest(
    packs_dir: Path,
) -> None:
    zip_path = packs_dir / "global_detail.zip"

    _write_zip(zip_path, {"chunks/cities/c3r9.json": _chunk_payload()})
    assert map_packs.install_pack_zip("global_detail", zip_path) == (
        "pack zip has no manifest.json"
    )

    _write_zip(zip_path, {"manifest.json": b"{not json"})
    assert "pack manifest unreadable" in map_packs.install_pack_zip(
        "global_detail", zip_path
    )

    oversized = b" " * (map_packs._MAX_MANIFEST_BYTES + 1)
    _write_zip(zip_path, {"manifest.json": oversized})
    error = map_packs.install_pack_zip("global_detail", zip_path)
    assert "pack manifest unreadable" in error
    assert "size limit" in error
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_invalid_total_bytes(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    chunk = _chunk_payload()

    for total_bytes, expected in (
        (-5, "invalid total_bytes"),
        (map_packs._MAX_INSTALLED_PACK_BYTES + 1, "exceeds installed size limit"),
        ("not a number", "invalid total_bytes"),
    ):
        manifest = _manifest_for_chunk(chunk, total_bytes=total_bytes)
        _write_zip(
            zip_path,
            {
                "manifest.json": json.dumps(manifest).encode("utf-8"),
                "chunks/cities/c3r9.json": chunk,
            },
        )
        error = map_packs.install_pack_zip("global_detail", zip_path)
        assert expected in error
        assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_chunk_without_byte_count(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    chunk = _chunk_payload()
    manifest = _manifest_for_chunk(chunk)
    del manifest["layers"]["cities"]["chunks"]["c3r9"]["bytes"]
    _write_zip(
        zip_path,
        {
            "manifest.json": json.dumps(manifest).encode("utf-8"),
            "chunks/cities/c3r9.json": chunk,
        },
    )

    assert "invalid byte count" in map_packs.install_pack_zip("global_detail", zip_path)


def test_install_pack_zip_rejects_missing_chunk_member(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    chunk = _chunk_payload()
    manifest = _manifest_for_chunk(chunk)
    _write_zip(zip_path, {"manifest.json": json.dumps(manifest).encode("utf-8")})

    error = map_packs.install_pack_zip("global_detail", zip_path)
    assert "missing chunk" in error
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_cumulative_size_over_limit(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    chunk = _chunk_payload()
    manifest = _manifest_for_chunk(chunk, total_bytes=map_packs._MAX_INSTALLED_PACK_BYTES)
    manifest["layers"]["cities"]["chunks"]["c9r9"] = {
        "path": "chunks/cities/c9r9.json",
        "bytes": map_packs._MAX_INSTALLED_PACK_BYTES,
        "sha256": "",
        "features": 1,
    }
    _write_zip(
        zip_path,
        {
            "manifest.json": json.dumps(manifest).encode("utf-8"),
            "chunks/cities/c3r9.json": chunk,
        },
    )

    error = map_packs.install_pack_zip("global_detail", zip_path)
    assert error == "pack exceeds installed size limit"
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_rejects_corrupt_zip(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    zip_path.write_bytes(b"this is not a zip archive")

    error = map_packs.install_pack_zip("global_detail", zip_path)
    assert error.startswith("pack install failed:")
    assert not (packs_dir / ".install-global_detail.tmp").exists()


def test_install_pack_zip_replaces_existing_install_and_stale_staging(
    packs_dir: Path,
) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    staging = packs_dir / ".install-global_detail.tmp"
    staging.mkdir()
    (staging / "leftover.txt").write_text("stale", encoding="utf-8")

    assert map_packs.install_pack_zip("global_detail", zip_path) == ""
    assert map_packs.load_installed_manifest("global_detail") is not None
    assert not staging.exists()


def test_install_pack_zip_reports_activation_failure(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)

    def _broken_replace(src: object, dst: object) -> None:
        raise OSError("activation blocked")

    monkeypatch.setattr(map_packs.os, "replace", _broken_replace)
    error = map_packs.install_pack_zip("global_detail", zip_path)

    assert error.startswith("pack install failed while activating:")
    assert not (packs_dir / ".install-global_detail.tmp").exists()
    assert map_packs.load_installed_manifest("global_detail") is None


def test_remove_installed_pack_reports_delete_failure(
    packs_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    def _broken_rmtree(path: object, **kwargs: object) -> None:
        raise OSError("delete blocked")

    monkeypatch.setattr(map_packs.shutil, "rmtree", _broken_rmtree)
    error = map_packs.remove_installed_pack("global_detail")
    assert error.startswith("failed to delete pack:")


def test_status_payload_lists_unknown_sideload_zip(packs_dir: Path) -> None:
    (packs_dir / "region_custom.zip").write_bytes(b"placeholder zip bytes")

    payload = map_packs.map_pack_status_payload()
    entry = next(p for p in payload["packs"] if p["id"] == "region_custom")
    assert entry["state"] == "sideload_ready"
    assert entry["sideload_ready"] is True
    assert "--download" not in entry["install_command"]


def test_installed_pack_summary_tolerates_bad_numbers(packs_dir: Path) -> None:
    chunk = _chunk_payload()
    manifest = _manifest_for_chunk(
        chunk, pack_id="region_weird", total_bytes=["bad"], version=["bad"]
    )
    install_dir = packs_dir / "region_weird"
    (install_dir / "chunks" / "cities").mkdir(parents=True)
    (install_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (install_dir / "chunks" / "cities" / "c3r9.json").write_bytes(chunk)

    payload = map_packs.map_pack_status_payload()
    entry = next(p for p in payload["packs"] if p["id"] == "region_weird")
    assert entry["installed"] is True
    assert entry["installed_pack"]["total_bytes"] == 0
    assert entry["installed_pack"]["version"] == 0
    assert entry["installed_pack"]["chunk_count"] == 1


def test_load_map_pack_manifest_payload_errors(packs_dir: Path) -> None:
    invalid = map_packs.load_map_pack_manifest_payload("Bad Id!")
    assert invalid == {"ok": False, "error": "invalid pack id", "http_status": 400}

    missing = map_packs.load_map_pack_manifest_payload("global_detail")
    assert missing == {"ok": False, "error": "pack is not installed", "http_status": 404}


def test_read_chunk_rejects_symlink_escape(packs_dir: Path, tmp_path: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    chunk_path = packs_dir / "global_detail" / "chunks" / "cities" / "c3r9.json"
    chunk_path.unlink()
    chunk_path.symlink_to(outside)

    assert map_packs.read_map_pack_chunk("global_detail", "chunks/cities/c3r9.json") is None


def test_python_command_path_fallbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(map_packs, "_app_dir", lambda: tmp_path / "app")
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "executable", "")
    assert map_packs._python_command_path() == "python"

    monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
    assert map_packs._python_command_path() == "python"

    monkeypatch.setattr(sys, "executable", str(tmp_path / "venvx" / "python"))
    assert map_packs._python_command_path() == "venvx/python"


def test_dashboard_routes_serve_pack_endpoints(packs_dir: Path) -> None:
    zip_path = packs_dir / "global_detail.zip"
    _build_pack_zip(zip_path)
    assert map_packs.install_pack_zip("global_detail", zip_path) == ""

    from meshdash.http_routes_get import handle_dashboard_get

    captured: dict[str, object] = {}

    class _FakeHandler:
        headers: dict[str, str] = {}

        def send_response(self, code: int) -> None:
            captured["status"] = code

        def send_header(self, key: str, value: str) -> None:
            captured.setdefault("headers", {})[key] = value  # type: ignore[union-attr]

        def end_headers(self) -> None:
            pass

        class _Wfile:
            @staticmethod
            def write(payload: bytes) -> None:
                captured["body"] = payload

        wfile = _Wfile()

    def _write_json(handler, *, status_code, payload_obj, no_store=False, extra_headers=None):
        captured["status"] = status_code
        captured["json"] = payload_obj

    def _write_text(handler, *, status_code, text):
        captured["status"] = status_code
        captured["text"] = text

    class _Deps:
        write_json_response_fn = staticmethod(_write_json)
        write_text_response_fn = staticmethod(_write_text)
        private_mode = False
        api_metrics = None

    handler = _FakeHandler()

    handle_dashboard_get(handler, path="/api/maps/packs", query="", deps=_Deps())
    assert captured["status"] == 200
    assert captured["json"]["ok"] is True

    handle_dashboard_get(handler, path="/api/maps/pack/global_detail/manifest", query="", deps=_Deps())
    assert captured["status"] == 200
    assert captured["json"]["id"] == "global_detail"

    captured.clear()
    handle_dashboard_get(
        handler, path="/api/maps/pack/global_detail/chunks/cities/c3r9.json", query="", deps=_Deps()
    )
    assert captured["status"] == 200
    assert captured["body"] == _chunk_payload()

    captured.clear()
    handle_dashboard_get(
        handler, path="/api/maps/pack/global_detail/chunks/cities/nope.json", query="", deps=_Deps()
    )
    assert captured["status"] == 404
