import json
from dataclasses import dataclass


@dataclass(frozen=True)
class StandaloneZorkRequest:
    text: object
    session_id: object


def parse_standalone_zork_request(raw_body: bytes) -> StandaloneZorkRequest:
    try:
        body = json.loads(raw_body.decode("utf-8"))
    except Exception:
        body = {}
    payload = body if isinstance(body, dict) else {}
    return StandaloneZorkRequest(
        text=payload.get("text"),
        session_id=payload.get("session_id"),
    )


__all__ = [
    "StandaloneZorkRequest",
    "parse_standalone_zork_request",
]
