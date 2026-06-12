from animator_credit_monitor.models import RunReport, SourcePlan, SourceRunResult
from animator_credit_monitor.ports import HistoryRepository, NotificationGateway


class MonitorUseCase:
    def __init__(self, history: HistoryRepository, notifier: NotificationGateway) -> None:
        self._history = history
        self._notifier = notifier

    def run(self, plans: list[SourcePlan], *, dry_run: bool) -> RunReport:
        results: list[SourceRunResult] = []
        for plan in plans:
            results.append(self._run_source(plan, dry_run=dry_run))
        return RunReport(source_results=results)

    def _run_source(self, plan: SourcePlan, *, dry_run: bool) -> SourceRunResult:
        items = plan.fetch_credits()
        if not items:
            return SourceRunResult(
                plan=plan,
                had_data=False,
                diff_count=0,
                notification_error=None,
                saved_history=False,
            )

        diff = self._history.detect_diff(plan.source_key, items)
        notification_error: str | None = None
        if diff:
            try:
                self._notifier.notify(plan.notification_title, plan.format_diff(diff))
            except Exception as e:
                notification_error = str(e)

        saved_history = False
        if not dry_run and notification_error is None:
            self._history.save(plan.source_key, items)
            saved_history = True

        return SourceRunResult(
            plan=plan,
            had_data=True,
            diff_count=len(diff),
            notification_error=notification_error,
            saved_history=saved_history,
        )
