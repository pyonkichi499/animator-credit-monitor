from unittest.mock import MagicMock

import pytest

from animator_credit_monitor.delivery import DeliveryTarget, RetryPolicy
from animator_credit_monitor.firestore_usecase import (
    FirestoreOutboxMonitorUseCase,
    FirestoreRuntimeContext,
)
from animator_credit_monitor.models import SourcePlan

# ---- helpers ----


def _make_deps() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """snapshots, runs, outbox, dispatcher のモックを生成する。"""
    snapshots: MagicMock = MagicMock()
    runs: MagicMock = MagicMock()
    outbox: MagicMock = MagicMock()
    dispatcher: MagicMock = MagicMock()
    return snapshots, runs, outbox, dispatcher


def _make_usecase(
    snapshots: MagicMock,
    runs: MagicMock,
    outbox: MagicMock,
    dispatcher: MagicMock,
    retry_policy: RetryPolicy | None = None,
) -> FirestoreOutboxMonitorUseCase:
    policy = retry_policy or RetryPolicy(max_retries=2, initial_delay_seconds=60)
    return FirestoreOutboxMonitorUseCase(snapshots, runs, outbox, dispatcher, policy)


def _make_plan(
    *,
    items: list[dict] | None = None,
    diff: list[dict] | None = None,
    short_name: str = "Bangumi",
) -> SourcePlan:
    """テスト用 SourcePlan を生成する。"""
    fetch = MagicMock(return_value=items if items is not None else [])
    fmt = MagicMock(return_value="formatted diff message")
    return SourcePlan(
        short_name=short_name,
        label=f"{short_name} label",
        source_key=f"{short_name.lower()}_key",
        notification_title=f"新しいクレジット ({short_name})",
        fetch_credits=fetch,
        format_diff=fmt,
        source_type="bangumi",
        target_label="テスト対象",
    )


def _context() -> FirestoreRuntimeContext:
    return FirestoreRuntimeContext(runtime="github-actions", trigger_type="schedule")


# ---- run() 全体フロー ----


class TestFirestoreOutboxMonitorUseCaseRun:
    def test_データ取得が空の場合はhad_dataがFalseになる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        plan = _make_plan(items=[])
        report = uc.run([plan], dry_run=False, context=_context())

        assert report.checks_run == 1
        assert report.source_results[0].had_data is False
        snapshots.detect_diff.assert_not_called()

    def test_差分なしの場合は通知せずに履歴を保存する(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        snapshots.detect_diff.return_value = []
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        items = [{"id": "1", "title": "作品A"}]
        plan = _make_plan(items=items)
        report = uc.run([plan], dry_run=False, context=_context())

        assert report.source_results[0].had_data is True
        assert report.source_results[0].diff_count == 0
        assert report.source_results[0].saved_history is True
        snapshots.save.assert_called_once()
        outbox.create_event_and_deliveries.assert_not_called()

    def test_差分ありの場合はoutboxに書き込んで配信する(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        diff = [{"id": "2", "title": "新作品"}]
        snapshots.detect_diff.return_value = diff
        outbox.create_event_and_deliveries.return_value = ("ev-1", ["dl-1"])
        outbox.get_delivery.return_value = {"id": "dl-1", "channel": "console", "attemptCount": 0}
        outbox.mark_delivery_sent.return_value = "ev-1"
        target = DeliveryTarget(channel="console", destination_key="stdout", notifier=MagicMock())
        dispatcher.targets = [target]
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        items = [{"id": "1"}, {"id": "2", "title": "新作品"}]
        plan = _make_plan(items=items)
        report = uc.run([plan], dry_run=False, context=_context())

        assert report.source_results[0].diff_count == 1
        assert report.source_results[0].saved_history is True
        outbox.create_event_and_deliveries.assert_called_once()
        dispatcher.send.assert_called_once()

    def test_dry_runの場合はoutboxに書き込まず直接配信する(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        diff = [{"id": "2"}]
        snapshots.detect_diff.return_value = diff
        target = DeliveryTarget(channel="console", destination_key="stdout", notifier=MagicMock())
        dispatcher.targets = [target]
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        plan = _make_plan(items=[{"id": "1"}, {"id": "2"}])
        report = uc.run([plan], dry_run=True, context=_context())

        assert report.source_results[0].diff_count == 1
        assert report.source_results[0].saved_history is False
        outbox.create_event_and_deliveries.assert_not_called()
        dispatcher.send.assert_called_once()

    def test_配信失敗時はpartial_failureになる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        diff = [{"id": "2"}]
        snapshots.detect_diff.return_value = diff
        outbox.create_event_and_deliveries.return_value = ("ev-1", ["dl-1"])
        outbox.get_delivery.return_value = {"id": "dl-1", "channel": "email", "attemptCount": 0}
        dispatcher.send.side_effect = RuntimeError("SMTP error")
        outbox.mark_delivery_failed.return_value = "ev-1"
        target = DeliveryTarget(channel="email", destination_key="user@test.com", notifier=MagicMock())
        dispatcher.targets = [target]
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        plan = _make_plan(items=[{"id": "1"}, {"id": "2"}])
        report = uc.run([plan], dry_run=False, context=_context())

        assert report.run_status == "partial_failure"
        assert report.source_results[0].notification_error is not None
        outbox.mark_delivery_failed.assert_called_once()

    def test_例外発生時もfinish_runが呼ばれる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.side_effect = RuntimeError("Firestore unavailable")
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        with pytest.raises(RuntimeError, match="Firestore unavailable"):
            uc.run([], dry_run=False, context=_context())

        runs.finish_run.assert_called_once()
        finish_kwargs = runs.finish_run.call_args
        assert finish_kwargs[1]["status"] == "failed"

    def test_redelivery失敗がある場合はpartial_failureになる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        # redelivery: 1件あるが配信失敗
        retryable = [{"id": "dl-old", "channel": "email", "eventId": "ev-old", "attemptCount": 1}]
        outbox.list_retryable_deliveries.return_value = retryable
        outbox.get_event_payload.return_value = {"payload": {"title": "t", "message": "m"}}
        dispatcher.send.side_effect = RuntimeError("fail")
        outbox.mark_delivery_failed.return_value = "ev-old"
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        report = uc.run([], dry_run=False, context=_context())

        assert report.redelivery_processed == 1
        assert report.redelivery_failed == 1
        assert report.run_status == "partial_failure"


# ---- _process_redeliveries ----


class TestProcessRedeliveries:
    def test_リトライ可能な配信がない場合は0を返す(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        report = uc.run([], dry_run=False, context=_context())

        assert report.redelivery_processed == 0
        assert report.redelivery_failed == 0

    def test_payloadが空の配信はスキップされる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        retryable = [{"id": "dl-1", "channel": "email", "eventId": "ev-1", "attemptCount": 0}]
        outbox.list_retryable_deliveries.return_value = retryable
        outbox.get_event_payload.return_value = {}  # payload なし
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        report = uc.run([], dry_run=False, context=_context())

        assert report.redelivery_processed == 0
        dispatcher.send.assert_not_called()

    def test_redelivery成功時はprocessed加算のみ(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        retryable = [{"id": "dl-1", "channel": "console", "eventId": "ev-1", "attemptCount": 1}]
        outbox.list_retryable_deliveries.return_value = retryable
        outbox.get_event_payload.return_value = {"payload": {"title": "t", "message": "m"}}
        outbox.mark_delivery_sent.return_value = "ev-1"
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        report = uc.run([], dry_run=False, context=_context())

        assert report.redelivery_processed == 1
        assert report.redelivery_failed == 0
        assert report.run_status == "success"


# ---- _dispatch_delivery_ids (delivery が見つからない場合) ----


class TestDispatchDeliveryIds:
    def test_deliveryが見つからない場合はスキップされる(self) -> None:
        snapshots, runs, outbox, dispatcher = _make_deps()
        runs.start_run.return_value = "run-1"
        outbox.list_retryable_deliveries.return_value = []
        diff = [{"id": "2"}]
        snapshots.detect_diff.return_value = diff
        outbox.create_event_and_deliveries.return_value = ("ev-1", ["dl-1"])
        outbox.get_delivery.return_value = None  # 見つからない
        target = DeliveryTarget(channel="console", destination_key="stdout", notifier=MagicMock())
        dispatcher.targets = [target]
        uc = _make_usecase(snapshots, runs, outbox, dispatcher)

        plan = _make_plan(items=[{"id": "1"}, {"id": "2"}])
        report = uc.run([plan], dry_run=False, context=_context())

        dispatcher.send.assert_not_called()
        assert report.source_results[0].notification_error is None
