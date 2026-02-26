from collections.abc import Sequence
from typing import Protocol

SqlValue = object
SqlRow = tuple[SqlValue, ...]
SqlRows = list[SqlRow]


class SqlCursor(Protocol):
    def fetchone(self) -> SqlRow | None:
        ...

    def fetchall(self) -> SqlRows:
        ...


class SqlConnection(Protocol):
    def execute(self, sql: str, parameters: Sequence[object] = ()) -> SqlCursor:
        ...

    def commit(self) -> None:
        ...

    def close(self) -> None:
        ...
