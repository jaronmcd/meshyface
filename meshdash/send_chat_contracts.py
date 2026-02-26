from typing import Optional, Protocol


class SendTextInterface(Protocol):
    def sendText(
        self,
        text: str,
        destinationId: str,
        wantAck: bool,
        channelIndex: int,
        replyId: Optional[int],
    ) -> object:
        ...


class SendLock(Protocol):
    def __enter__(self) -> object:
        ...

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        ...
