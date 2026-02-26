from typing import Protocol, cast

from .nodes import get_local_node_id as _get_local_node_id_helper
from .runtime_types import ToIntFn, ToJsonableFn


class PacketSender(Protocol):
    def _sendPacket(
        self,
        packet: object,
        *,
        destinationId: str,
        wantAck: bool,
    ) -> object:
        ...


def get_local_node_id(
    iface: object,
    *,
    meshtastic_module: object,
    to_jsonable_fn: ToJsonableFn,
    to_int_fn: ToIntFn,
) -> str:
    broadcast_num = (
        getattr(meshtastic_module, "BROADCAST_NUM", None)
        if meshtastic_module is not None
        else None
    )
    return _get_local_node_id_helper(
        iface,
        broadcast_num=broadcast_num,
        to_jsonable_fn=to_jsonable_fn,
        to_int_fn=to_int_fn,
    )


def send_emoji_reaction_packet(
    *,
    iface: object,
    destination_id: str,
    channel_index: int,
    reply_id: int,
    emoji_codepoint: int,
    emoji_text: str,
    want_ack: bool,
    mesh_pb2_module: object,
    portnums_pb2_module: object,
) -> object:
    if mesh_pb2_module is None or portnums_pb2_module is None:
        raise RuntimeError("Meshtastic protobuf modules are unavailable for emoji reactions")
    if not hasattr(iface, "_sendPacket"):
        raise RuntimeError("Meshtastic interface does not support low-level packet send")

    packet = mesh_pb2_module.MeshPacket()
    packet.channel = int(channel_index)
    packet.decoded.portnum = portnums_pb2_module.PortNum.TEXT_MESSAGE_APP
    packet.decoded.reply_id = int(reply_id)
    packet.decoded.emoji = int(emoji_codepoint)
    packet.decoded.payload = str(emoji_text or "").encode("utf-8")
    sender = cast(PacketSender, iface)
    return sender._sendPacket(packet, destinationId=destination_id, wantAck=bool(want_ack))
