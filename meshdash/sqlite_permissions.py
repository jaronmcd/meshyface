import os

PRIVATE_SQLITE_DIR_MODE = 0o700
PRIVATE_SQLITE_FILE_MODE = 0o600


def is_unmanaged_sqlite_path(db_path: object) -> bool:
    clean_path = str(db_path or "").strip()
    if not clean_path:
        return True

    lowered = clean_path.lower()
    if lowered in {":memory:", "file::memory:"}:
        return True
    if lowered.startswith("file:"):
        return True
    return False


def secure_sqlite_database_path(db_path: object) -> bool:
    clean_path = str(db_path or "").strip()
    if is_unmanaged_sqlite_path(clean_path):
        return False

    db_dir = os.path.dirname(clean_path)
    if db_dir:
        created_dir = not os.path.isdir(db_dir)
        os.makedirs(db_dir, mode=PRIVATE_SQLITE_DIR_MODE, exist_ok=True)
        if created_dir:
            os.chmod(db_dir, PRIVATE_SQLITE_DIR_MODE)

    flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        fd = os.open(clean_path, flags, PRIVATE_SQLITE_FILE_MODE)
    except FileExistsError:
        return False
    os.close(fd)
    return True


def secure_sqlite_sidecar_paths(db_path: object, *, created_database: bool = False) -> None:
    if not created_database:
        return

    clean_path = str(db_path or "").strip()
    if is_unmanaged_sqlite_path(clean_path):
        return

    for path in (
        clean_path,
        f"{clean_path}-journal",
        f"{clean_path}-shm",
        f"{clean_path}-wal",
    ):
        if os.path.exists(path):
            os.chmod(path, PRIVATE_SQLITE_FILE_MODE)
