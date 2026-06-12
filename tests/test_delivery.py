from unittest.mock import MagicMock

import pytest

from animator_credit_monitor.delivery import DeliveryDispatcher, DeliveryTarget, RetryPolicy


def _dispatcher(
    notifier: MagicMock,
    retry_policy: RetryPolicy,
    sleeper: MagicMock | None = None,
) -> DeliveryDispatcher:
    return DeliveryDispatcher(
        targets=[DeliveryTarget(channel="console", destination_key="stdout", notifier=notifier)],
        retry_policy=retry_policy,
        sleeper=sleeper or MagicMock(),
    )


def test_retry_dispatcherは成功まで指数バックオフで再試行する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = [RuntimeError("x"), RuntimeError("y"), None]
    sleeper = MagicMock()
    dispatcher = _dispatcher(notifier, RetryPolicy(max_retries=2, initial_delay_seconds=60), sleeper)

    dispatcher.send("console", "title", "message")

    assert notifier.notify.call_count == 3
    sleeper.assert_any_call(60.0)
    sleeper.assert_any_call(120.0)


def test_retry_dispatcherは上限到達で例外を再送出する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = RuntimeError("fail")
    dispatcher = _dispatcher(notifier, RetryPolicy(max_retries=1, initial_delay_seconds=0))

    with pytest.raises(RuntimeError):
        dispatcher.send("console", "title", "message")


def test_初回成功時は再試行もsleepもしない() -> None:
    notifier = MagicMock()
    sleeper = MagicMock()
    dispatcher = _dispatcher(notifier, RetryPolicy(max_retries=2, initial_delay_seconds=60), sleeper)

    dispatcher.send("console", "title", "message")

    notifier.notify.assert_called_once_with("title", "message")
    sleeper.assert_not_called()


def test_max_retriesが0の場合は1回だけ試行して失敗する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = RuntimeError("fail")
    sleeper = MagicMock()
    dispatcher = _dispatcher(notifier, RetryPolicy(max_retries=0, initial_delay_seconds=60), sleeper)

    with pytest.raises(RuntimeError):
        dispatcher.send("console", "title", "message")

    assert notifier.notify.call_count == 1
    sleeper.assert_not_called()


def test_initial_delayが0の場合はsleepせず再試行する() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = [RuntimeError("x"), None]
    sleeper = MagicMock()
    dispatcher = _dispatcher(notifier, RetryPolicy(max_retries=1, initial_delay_seconds=0), sleeper)

    dispatcher.send("console", "title", "message")

    assert notifier.notify.call_count == 2
    sleeper.assert_not_called()


def test_backoff_multiplierのカスタム値が反映される() -> None:
    notifier = MagicMock()
    notifier.notify.side_effect = [RuntimeError("x"), RuntimeError("y"), None]
    sleeper = MagicMock()
    dispatcher = _dispatcher(
        notifier,
        RetryPolicy(max_retries=2, initial_delay_seconds=10, backoff_multiplier=3),
        sleeper,
    )

    dispatcher.send("console", "title", "message")

    sleeper.assert_any_call(10.0)
    sleeper.assert_any_call(30.0)


def test_未知のチャネルへの送信はKeyErrorになる() -> None:
    dispatcher = _dispatcher(MagicMock(), RetryPolicy(max_retries=0, initial_delay_seconds=0))

    with pytest.raises(KeyError):
        dispatcher.send("unknown", "title", "message")


def test_targetsプロパティは登録済みターゲットを返す() -> None:
    target_console = DeliveryTarget(channel="console", destination_key="stdout", notifier=MagicMock())
    target_email = DeliveryTarget(channel="email", destination_key="to@example.com", notifier=MagicMock())
    dispatcher = DeliveryDispatcher(
        targets=[target_console, target_email],
        retry_policy=RetryPolicy(max_retries=0, initial_delay_seconds=0),
        sleeper=MagicMock(),
    )

    assert dispatcher.targets == [target_console, target_email]


def test_同一チャネルの後勝ち登録で上書きされる() -> None:
    first = MagicMock()
    second = MagicMock()
    dispatcher = DeliveryDispatcher(
        targets=[
            DeliveryTarget(channel="console", destination_key="a", notifier=first),
            DeliveryTarget(channel="console", destination_key="b", notifier=second),
        ],
        retry_policy=RetryPolicy(max_retries=0, initial_delay_seconds=0),
        sleeper=MagicMock(),
    )

    dispatcher.send("console", "title", "message")

    first.notify.assert_not_called()
    second.notify.assert_called_once()
