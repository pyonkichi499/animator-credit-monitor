from unittest.mock import MagicMock

import pytest

from animator_credit_monitor.delivery import DeliveryDispatcher, DeliveryTarget, RetryPolicy


def test_retry_dispatcherは成功まで指数バックオフで再試行する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = [RuntimeError("x"), RuntimeError("y"), None]
    sleeper = MagicMock()
    dispatcher = DeliveryDispatcher(
        targets=[DeliveryTarget(channel="console", destination_key="stdout", notifier=notifier)],
        retry_policy=RetryPolicy(max_retries=2, initial_delay_seconds=60),
        sleeper=sleeper,
    )

    dispatcher.send("console", "title", "message")

    assert notifier.notify.call_count == 3
    sleeper.assert_any_call(60.0)
    sleeper.assert_any_call(120.0)


def test_retry_dispatcherは上限到達で例外を再送出する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = RuntimeError("fail")
    dispatcher = DeliveryDispatcher(
        targets=[DeliveryTarget(channel="console", destination_key="stdout", notifier=notifier)],
        retry_policy=RetryPolicy(max_retries=1, initial_delay_seconds=0),
        sleeper=MagicMock(),
    )

    with pytest.raises(RuntimeError):
        dispatcher.send("console", "title", "message")
