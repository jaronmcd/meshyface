import json
import time
from typing import Optional, Protocol

from .helpers import to_int
from .history_malformed_text import save_malformed_text_payload as _save_malformed_text_payload_helper
from .sql_contracts import SqlConnection


class NowUnixFn(Protocol):
    def __call__(self) -> float:
        ...


class SavePacketEventAndRollupsFn(Protocol):
    def __call__(
        self,
        conn: SqlConnection,
        summary: dict[str, object],
        *,
        packet: dict[str, object] | None = None,
        now_unix_fn: NowUnixFn,
        custom_telemetry_rules: object = None,
    ) -> None:
        ...


def save_packet_record(
    conn: SqlConnection,
    packet_entry: dict[str, object],
    *,
    now_unix_fn: NowUnixFn = time.time,
    save_packet_event_and_rollups_fn: Optional[SavePacketEventAndRollupsFn] = None,
    custom_telemetry_rules: object = None,
) -> None:
    summary = packet_entry.get("summary")
    packet = packet_entry.get("packet")
    summary_json = json.dumps(summary, separators=(",", ":"))
    packet_json = json.dumps(packet, separators=(",", ":"))
    created_unix = int(now_unix_fn())

    cursor = conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        (created_unix, summary_json, packet_json),
    )
    packet_row_id = int(getattr(cursor, "lastrowid", 0) or 0)
    if packet_row_id > 0:
        _save_malformed_text_payload_helper(
            conn,
            created_unix=created_unix,
            packet_row_id=packet_row_id,
            summary=summary if isinstance(summary, dict) else None,
            packet=packet if isinstance(packet, dict) else None,
        )
    if isinstance(summary, dict) and save_packet_event_and_rollups_fn is not None:
        save_packet_event_and_rollups_fn(
            conn,
            summary,
            packet=packet if isinstance(packet, dict) else None,
            now_unix_fn=now_unix_fn,
            custom_telemetry_rules=custom_telemetry_rules,
        )


def save_chat_record(
    conn: SqlConnection,
    chat_entry: dict[str, object],
    *,
    now_unix_fn: NowUnixFn = time.time,
) -> None:
    message_json = json.dumps(chat_entry, separators=(",", ":"))
    conn.execute(
        "INSERT INTO chat(created_unix, message_json) VALUES(?, ?)",
        (int(now_unix_fn()), message_json),
    )


def update_chat_record(
    conn: SqlConnection,
    chat_entry: dict[str, object],
) -> bool:
    message_id = to_int(
        chat_entry.get("message_id")
        or chat_entry.get("messageId")
        or chat_entry.get("packet_id")
        or chat_entry.get("packetId")
    )
    if message_id is None or message_id <= 0:
        return False
    message_json = json.dumps(chat_entry, separators=(",", ":"))
    cursor = conn.execute(
        """
        UPDATE chat
        SET message_json = ?
        WHERE id = (
          SELECT id
          FROM chat
          WHERE json_extract(message_json, '$.local_echo') = 1
            AND CAST(
              COALESCE(
                json_extract(message_json, '$.message_id'),
                json_extract(message_json, '$.messageId'),
                json_extract(message_json, '$.packet_id'),
                json_extract(message_json, '$.packetId')
              ) AS INTEGER
            ) = ?
          ORDER BY id DESC
          LIMIT 1
        )
        """,
        (message_json, int(message_id)),
    )
    return int(getattr(cursor, "rowcount", 0) or 0) > 0
