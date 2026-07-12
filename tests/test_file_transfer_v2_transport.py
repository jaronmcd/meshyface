from pathlib import Path

import pytest

from meshdash.file_transfer_protocol import (
    FILE_TRANSFER_CHUNK_BYTES,
    FILE_TRANSFER_PORTNUM,
    build_file_transfer_ack_frame,
    decode_file_transfer_packet,
    decode_file_transfer_payload,
    encode_file_transfer_frame,
    file_transfer_frame_text,
    parse_file_transfer_frame_text,
)
from meshdash.services_chat import send_chat_message
from meshdash.tracker_entries import build_packet_summary


class _Lock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Iface:
    def __init__(self) -> None:
        self.data_calls: list[tuple[bytes, dict[str, object]]] = []
        self.text_calls: list[tuple[str, dict[str, object]]] = []

    def sendData(self, payload: bytes, **kwargs: object) -> dict[str, int]:
        self.data_calls.append((bytes(payload), dict(kwargs)))
        return {"id": 1234}

    def sendText(self, text: str, **kwargs: object) -> dict[str, int]:
        self.text_calls.append((text, dict(kwargs)))
        return {"id": 5678}


@pytest.mark.parametrize(
    "fixture_name",
    [
        "file_transfer_1k.png",
        "file_transfer_2k.png",
        "file_transfer_4k.png",
        "file_transfer_8k.png",
        "file_transfer_16k.png",
        "file_transfer_32k.png",
        "file_transfer_64k.png",
    ],
)
def test_v2_packetizes_and_reconstructs_fixture_ladder(fixture_name: str) -> None:
    source = (Path(__file__).parent / "fixtures" / fixture_name).read_bytes()
    chunks = [
        source[offset : offset + FILE_TRANSFER_CHUNK_BYTES]
        for offset in range(0, len(source), FILE_TRANSFER_CHUNK_BYTES)
    ]
    transfer_id = "fixtureladder123"
    metadata = {
        "kind": "meta",
        "transfer_id": transfer_id,
        "file_name": fixture_name,
        "file_size": len(source),
        "original_file_size": len(source),
        "total_chunks": len(chunks),
        "codec": "raw",
    }

    decoded_meta = decode_file_transfer_payload(encode_file_transfer_frame(metadata))
    decoded_chunks = [
        decode_file_transfer_payload(
            encode_file_transfer_frame(
                {
                    "kind": "chunk",
                    "transfer_id": transfer_id,
                    "chunk_index": index,
                    "chunk_bytes": chunk,
                }
            )
        )
        for index, chunk in enumerate(chunks)
    ]

    assert decoded_meta is not None
    assert decoded_meta["file_size"] == len(source)
    assert decoded_meta["total_chunks"] == len(chunks)
    assert b"".join(frame["chunk_bytes"] for frame in decoded_chunks if frame) == source
    assert all(
        len(
            encode_file_transfer_frame(
                {
                    "kind": "chunk",
                    "transfer_id": transfer_id,
                    "chunk_index": index,
                    "chunk_bytes": chunk,
                }
            )
        )
        <= 233
        for index, chunk in enumerate(chunks)
    )

    ack_text = build_file_transfer_ack_frame(
        transfer_id=transfer_id,
        total_chunks=len(chunks),
        received_indexes=range(len(chunks)),
    )
    ack_frame = parse_file_transfer_frame_text(ack_text)
    assert ack_frame is not None
    assert ack_frame["received_count"] == len(chunks)
    assert len(encode_file_transfer_frame(ack_frame)) <= 233


@pytest.mark.parametrize(
    "text",
    [
        "MF_FILE_V2|M|abcd1234|hello%20mesh.bin|320|2|raw|320",
        "MF_FILE_V2|C|abcd1234|1|AQIDBA==",
        "MF_FILE_V2|A|abcd1234|1|2|AQ==",
        "MF_FILE_V2|F|abcd1234|P",
    ],
)
def test_v2_binary_codec_round_trips_protocol_frames(text: str) -> None:
    frame = parse_file_transfer_frame_text(text)
    assert frame is not None

    payload = encode_file_transfer_frame(frame)
    decoded = decode_file_transfer_payload(payload)

    assert decoded is not None
    assert file_transfer_frame_text(decoded) == text
    assert len(payload) <= 233


def test_v1_text_is_not_recognized() -> None:
    assert parse_file_transfer_frame_text(
        "MF_FILE_V1|C|abcd1234|0|AQID"
    ) is None


def test_file_frame_uses_send_data_on_dedicated_port() -> None:
    iface = _Iface()

    response = send_chat_message(
        text="MF_FILE_V2|C|abcd1234|0|AQID",
        destination="!01020304",
        channel_index=2,
        iface=iface,
        send_lock=_Lock(),
        send_reaction_packet_fn=lambda **_kwargs: None,
        local_node_id_fn=lambda: "!12345678",
        record_local_chat_fn=lambda **_kwargs: None,
        chat_max_bytes=200,
        normalize_single_emoji_fn=lambda _value: (None, None),
        to_int_fn=lambda value: int(value) if value is not None else None,
        now_text_fn=lambda: "now",
    )

    assert iface.text_calls == []
    assert len(iface.data_calls) == 1
    payload, kwargs = iface.data_calls[0]
    assert kwargs == {
        "destinationId": "!01020304",
        "portNum": FILE_TRANSFER_PORTNUM,
        "wantAck": False,
        "wantResponse": False,
        "channelIndex": 2,
    }
    assert decode_file_transfer_payload(payload)["chunk_bytes"] == b"\x01\x02\x03"
    assert response["protocol"] == "MF_FILE_V2"
    assert response["packet_id"] == 1234


def test_v2_packet_is_exposed_as_protocol_text_in_packet_summary() -> None:
    frame = parse_file_transfer_frame_text("MF_FILE_V2|A|abcd1234|1|2|AQ==")
    assert frame is not None
    packet = {
        "from": 0x01020304,
        "to": 0x12345678,
        "channel": 2,
        "decoded": {
            "portnum": FILE_TRANSFER_PORTNUM,
            "payload": encode_file_transfer_frame(frame),
        },
    }

    assert decode_file_transfer_packet(packet) is not None
    summary = build_packet_summary(
        packet=packet,
        decoded=packet["decoded"],
        from_id="!01020304",
        to_id="!12345678",
        packet_id=22,
        rx_time=10,
        hops=1,
        reply_id=None,
        emoji_glyph=None,
        emoji_codepoint=None,
        is_reaction=False,
        packet_position=None,
        packet_battery=None,
        utc_now_fn=lambda: "now",
        format_epoch_fn=lambda _value: "then",
        to_int_fn=lambda value: int(value) if value is not None else None,
    )

    assert summary["decoded_text"] == "MF_FILE_V2|A|abcd1234|1|2|AQ=="
    assert summary["portnum"] == str(FILE_TRANSFER_PORTNUM)


def test_v2_rejects_broadcast_file_transfer() -> None:
    iface = _Iface()
    with pytest.raises(ValueError, match="direct destination"):
        send_chat_message(
            text="MF_FILE_V2|C|abcd1234|0|AQID",
            destination="^all",
            channel_index=0,
            iface=iface,
            send_lock=_Lock(),
            send_reaction_packet_fn=lambda **_kwargs: None,
            local_node_id_fn=lambda: "!12345678",
            record_local_chat_fn=lambda **_kwargs: None,
            chat_max_bytes=200,
            normalize_single_emoji_fn=lambda _value: (None, None),
            to_int_fn=lambda value: int(value) if value is not None else None,
            now_text_fn=lambda: "now",
        )
