from collections.abc import Sequence

from .history_metric_upsert_queries import (
    METRIC_FIELDS as _METRIC_FIELDS,
)
from .history_metric_upsert_queries import (
    where_clause as _where_clause,
)
from .sql_contracts import SqlConnection


def insert_metric_row(
    conn: SqlConnection,
    *,
    table_name: str,
    key_fields: Sequence[str],
    bucket_unix: int,
    key_values: Sequence[object],
    rolled: dict[str, object],
) -> None:
    fields = ("bucket_unix", *key_fields, *_METRIC_FIELDS)
    placeholders = ", ".join("?" for _ in fields)
    sql = f"INSERT INTO {table_name}({', '.join(fields)}) VALUES({placeholders})"
    values = (bucket_unix, *key_values, *[rolled[field] for field in _METRIC_FIELDS])
    conn.execute(sql, values)


def update_metric_row(
    conn: SqlConnection,
    *,
    table_name: str,
    key_fields: Sequence[str],
    bucket_unix: int,
    key_values: Sequence[object],
    merged: dict[str, object],
) -> None:
    assignments = ", ".join(f"{field} = ?" for field in _METRIC_FIELDS)
    sql = (
        f"UPDATE {table_name} "
        f"SET {assignments} "
        f"WHERE {_where_clause(key_fields=key_fields)}"
    )
    values = (*[merged[field] for field in _METRIC_FIELDS], bucket_unix, *key_values)
    conn.execute(sql, values)
