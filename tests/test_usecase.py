from unittest.mock import MagicMock

from animator_credit_monitor.models import RunReport, SourcePlan, SourceRunResult
from animator_credit_monitor.usecase import MonitorUseCase


def _make_plan(
    *,
    items: list[dict] | None = None,
    diff: list[dict] | None = None,
    short_name: str = "test",
    source_key: str = "test_key",
) -> SourcePlan:
    """テスト用の SourcePlan を生成するヘルパー。"""
    fetch: MagicMock = MagicMock(return_value=items if items is not None else [])
    fmt: MagicMock = MagicMock(return_value="formatted diff")
    return SourcePlan(
        short_name=short_name,
        label="Test Source",
        source_key=source_key,
        notification_title="Test Title",
        fetch_credits=fetch,
        format_diff=fmt,
    )


def _make_deps() -> tuple[MagicMock, MagicMock]:
    """HistoryRepository と NotificationGateway のモックを返す。"""
    history: MagicMock = MagicMock()
    notifier: MagicMock = MagicMock()
    return history, notifier


# ---- 1. データ取得が空 ----

def test_データ取得が空の場合はhad_dataがFalseになる() -> None:
    history, notifier = _make_deps()
    plan = _make_plan(items=[])
    uc = MonitorUseCase(history=history, notifier=notifier)

    report: RunReport = uc.run([plan], dry_run=False)

    result: SourceRunResult = report.source_results[0]
    assert result.had_data is False
    assert result.diff_count == 0
    assert result.notification_error is None
    assert result.saved_history is False
    history.detect_diff.assert_not_called()
    notifier.notify.assert_not_called()
    history.save.assert_not_called()


# ---- 2. 差分なし ----

def test_差分なしの場合は通知せずに履歴を保存する() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = []

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    result: SourceRunResult = report.source_results[0]
    assert result.had_data is True
    assert result.diff_count == 0
    assert result.notification_error is None
    assert result.saved_history is True
    history.detect_diff.assert_called_once_with("test_key", items)
    notifier.notify.assert_not_called()
    history.save.assert_called_once_with("test_key", items)


# ---- 3. 差分あり ----

def test_差分ありの場合は通知して履歴を保存する() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}, {"id": "2", "title": "作品B"}]
    diff: list[dict] = [{"id": "2", "title": "作品B"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = diff

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    result: SourceRunResult = report.source_results[0]
    assert result.had_data is True
    assert result.diff_count == 1
    assert result.notification_error is None
    assert result.saved_history is True
    notifier.notify.assert_called_once()
    history.save.assert_called_once_with("test_key", items)


# ---- 4. dry_run ----

def test_dry_runの場合は履歴を保存しない() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    diff: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = diff

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=True)

    result: SourceRunResult = report.source_results[0]
    assert result.had_data is True
    assert result.diff_count == 1
    assert result.saved_history is False
    notifier.notify.assert_called_once()
    history.save.assert_not_called()


# ---- 5. 通知失敗 ----

def test_通知失敗時は履歴を保存せずエラーを記録する() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    diff: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = diff
    notifier.notify.side_effect = RuntimeError("SMTP connection failed")

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    result: SourceRunResult = report.source_results[0]
    assert result.had_data is True
    assert result.diff_count == 1
    assert result.notification_error == "SMTP connection failed"
    assert result.saved_history is False
    history.save.assert_not_called()


# ---- 6. 複数プラン ----

def test_複数プランを順番に実行する() -> None:
    history, notifier = _make_deps()
    items_a: list[dict] = [{"id": "1", "title": "作品A"}]
    items_b: list[dict] = [{"id": "2", "title": "作品B"}]
    plan_a = _make_plan(items=items_a, short_name="a", source_key="key_a")
    plan_b = _make_plan(items=items_b, short_name="b", source_key="key_b")

    diff_b: list[dict] = [{"id": "2", "title": "作品B"}]
    history.detect_diff.side_effect = [
        [],       # plan_a: 差分なし
        diff_b,   # plan_b: 差分あり
    ]

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan_a, plan_b], dry_run=False)

    assert len(report.source_results) == 2

    result_a: SourceRunResult = report.source_results[0]
    assert result_a.had_data is True
    assert result_a.diff_count == 0
    assert result_a.saved_history is True

    result_b: SourceRunResult = report.source_results[1]
    assert result_b.had_data is True
    assert result_b.diff_count == 1
    assert result_b.saved_history is True

    # 通知は plan_b でのみ呼ばれる
    notifier.notify.assert_called_once()


# ---- 7. RunReport プロパティ ----

def test_RunReportのfound_newは差分ありソースがあればTrueを返す() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = [{"id": "1", "title": "作品A"}]

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    assert report.found_new is True
    assert report.checks_run == 1
    assert report.sources_with_new_credits == 1
    assert report.had_errors is False


def test_RunReportのfound_newは差分がなければFalseを返す() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = []

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    assert report.found_new is False
    assert report.checks_run == 1
    assert report.sources_with_new_credits == 0


def test_RunReportのhad_errorsは通知エラーがあればTrueを返す() -> None:
    history, notifier = _make_deps()
    items: list[dict] = [{"id": "1", "title": "作品A"}]
    plan = _make_plan(items=items)
    history.detect_diff.return_value = [{"id": "1", "title": "作品A"}]
    notifier.notify.side_effect = RuntimeError("fail")

    uc = MonitorUseCase(history=history, notifier=notifier)
    report: RunReport = uc.run([plan], dry_run=False)

    assert report.had_errors is True
