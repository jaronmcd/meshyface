from typing import Protocol


class RuntimeServer(Protocol):
    def serve_forever(self, poll_interval: float = 0.5) -> None:
        ...

    def server_close(self) -> None:
        ...


class CloseableResource(Protocol):
    def close(self) -> None:
        ...
