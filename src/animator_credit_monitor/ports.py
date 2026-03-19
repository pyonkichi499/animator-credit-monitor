from typing import Protocol


class HistoryRepository(Protocol):
    def detect_diff(self, source: str, new_data: list[dict]) -> list[dict]: ...

    def save(self, source: str, data: list[dict]) -> None: ...


class NotificationGateway(Protocol):
    def notify(self, title: str, message: str) -> None: ...

