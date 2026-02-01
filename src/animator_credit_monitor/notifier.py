from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def notify(self, title: str, message: str) -> None:
        ...


class ConsoleNotifier(Notifier):
    def notify(self, title: str, message: str) -> None:
        print(f"[{title}] {message}")
