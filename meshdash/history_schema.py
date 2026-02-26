from .history_schema_indexes import (
    INDEX_SCHEMA_STATEMENTS as _INDEX_SCHEMA_STATEMENTS,
)
from .history_schema_tables import (
    TABLE_SCHEMA_STATEMENTS as _TABLE_SCHEMA_STATEMENTS,
)
from .sql_contracts import SqlConnection


SCHEMA_STATEMENTS = _TABLE_SCHEMA_STATEMENTS + _INDEX_SCHEMA_STATEMENTS


def initialize_history_schema(conn: SqlConnection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
