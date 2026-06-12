from collections.abc import Callable
from dataclasses import dataclass
from time import sleep

from animator_credit_monitor.notifier import Notifier


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    initial_delay_seconds: int
    backoff_multiplier: int = 2


@dataclass(frozen=True)
class DeliveryTarget:
    channel: str
    destination_key: str
    notifier: Notifier


class DeliveryDispatcher:
    def __init__(
        self,
        targets: list[DeliveryTarget],
        retry_policy: RetryPolicy,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._targets_by_channel = {target.channel: target for target in targets}
        self._retry_policy = retry_policy
        self._sleep = sleeper

    @property
    def targets(self) -> list[DeliveryTarget]:
        return list(self._targets_by_channel.values())

    def send(self, channel: str, title: str, message: str) -> None:
        target = self._targets_by_channel[channel]
        self._send_with_retry(target.notifier, title, message)

    def _send_with_retry(self, notifier: Notifier, title: str, message: str) -> None:
        attempts = self._retry_policy.max_retries + 1
        delay = float(self._retry_policy.initial_delay_seconds)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                notifier.notify(title, message)
                return
            except Exception as e:
                last_error = e
                if attempt >= attempts - 1:
                    break
                if delay > 0:
                    self._sleep(delay)
                delay *= self._retry_policy.backoff_multiplier
        if last_error is not None:
            raise last_error

