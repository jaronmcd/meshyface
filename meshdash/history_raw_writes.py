import json
import time
from typing import Optional, Protocol

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
        now_unix_fn: NowUnixFn,
    ) -> None:
        ...


def save_packet_record(
    conn: SqlConnection,
    packet_entry: dict[str, object],
    *,
    now_unix_fn: NowUnixFn = time.time,
    save_packet_event_and_rollups_fn: Optional[SavePacketEventAndRollupsFn] = None,
) -> None:
    summary = packet_entry.get("summary")
    packet = packet_entry.get("packet")
    summary_json = json.dumps(summary, separators=(",", ":"))
    packet_json = json.dumps(packet, separators=(",", ":"))

    conn.execute(
        "INSERT INTO packets(created_unix, summary_json, packet_json) VALUES(?, ?, ?)",
        (int(now_unix_fn()), summary_json, packet_json),
    )
    if isinstance(summary, dict) and save_packet_event_and_rollups_fn is not None:
        save_packet_event_and_rollups_fn(conn, summary, now_unix_fn=now_unix_fn)


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
