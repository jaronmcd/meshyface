from pathlib import Path

from meshdash.sqlite_permissions import secure_sqlite_database_path


def test_secure_sqlite_database_path_skips_sqlite_file_uri_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert secure_sqlite_database_path("file:history.sqlite3?mode=rwc") is False
    assert list(tmp_path.iterdir()) == []
