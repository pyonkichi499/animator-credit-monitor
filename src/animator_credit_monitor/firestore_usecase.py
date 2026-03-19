import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from animator_credit_monitor.delivery import DeliveryDispatcher, RetryPolicy
from animator_credit_monitor.firestore_store import (
    FirestoreOutboxRepository,
    FirestoreRunRepository,
    FirestoreSnapshotRepository,
)
from animator_credit_monitor.models import RunReport, SourcePlan, SourceRunResult


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _dedupe_key(source_key: str, diff: list[dict]) -> str:
    serialized = json.dumps(diff, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(f"{source_key}:{serialized}".encode()).hexdigest()
    return f"{source_key}:{digest}"


def _next_retry_at_iso(*, current_attempt_count: int, retry_policy: RetryPolicy) -> str:
    exponent = max(current_attempt_count - 1, 0)
    delay = retry_policy.initial_delay_seconds * (retry_policy.backoff_multiplier**exponent)
    return _iso(_utcnow() + timedelta(seconds=delay))


@dataclass(frozen=True)
class FirestoreRuntimeContext:
    runtime: str
    trigger_type: str


class FirestoreOutboxMonitorUseCase:
    def __init__(
        self,
        snapshots: FirestoreSnapshotRepository,
        runs: FirestoreRunRepository,
        outbox: FirestoreOutboxRepository,
        dispatcher: DeliveryDispatcher,
        retry_policy: RetryPolicy,
    ) -> None:
        self._snapshots = snapshots
        self._runs = runs
        self._outbox = outbox
        self._dispatcher = dispatcher
        self._retry_policy = retry_policy

    def run(
        self,
        plans: list[SourcePlan],
        *,
        dry_run: bool,
        context: FirestoreRuntimeContext,
    ) -> RunReport:
        run_id = self._runs.start_run(runtime=context.runtime, trigger_type=context.trigger_type, dry_run=dry_run)
        source_results: list[SourceRunResult] = []
        errors: list[str] = []

        redelivery_processed, redelivery_failed = self._process_redeliveries()
        if redelivery_failed:
            errors.append(f"redelivery_failed={redelivery_failed}")

        for plan in plans:
            result = self._run_source(plan, run_id=run_id, dry_run=dry_run)
            source_results.append(result)
            if result.notification_error:
                errors.append(f"{plan.short_name}: {result.notification_error}")

        run_status = "success"
        if redelivery_failed or any(r.notification_error for r in source_results):
            run_status = "partial_failure"

        summary = {
            "checksRun": len(source_results),
            "sourcesWithNewCredits": sum(1 for r in source_results if r.diff_count > 0),
            "redeliveryProcessed": redelivery_processed,
            "redeliveryFailed": redelivery_failed,
        }
        self._runs.finish_run(run_id, status=run_status, summary=summary, errors=errors)

        return RunReport(
            source_results=source_results,
            redelivery_processed=redelivery_processed,
            redelivery_failed=redelivery_failed,
            run_status=run_status,
        )

    def _run_source(self, plan: SourcePlan, *, run_id: str, dry_run: bool) -> SourceRunResult:
        items = plan.fetch_credits()
        if not items:
            return SourceRunResult(
                plan=plan,
                had_data=False,
                diff_count=0,
                notification_error=None,
                saved_history=False,
            )

        diff = self._snapshots.detect_diff(plan.source_key, items)
        if not diff:
            if not dry_run:
                self._snapshots.save(plan.source_key, plan.source_type, plan.target_label or plan.label, items)
            return SourceRunResult(
                plan=plan,
                had_data=True,
                diff_count=0,
                notification_error=None,
                saved_history=not dry_run,
            )

        if dry_run:
            error = self._try_direct_dispatch(plan.notification_title, plan.format_diff(diff))
            return SourceRunResult(
                plan=plan,
                had_data=True,
                diff_count=len(diff),
                notification_error=error,
                saved_history=False,
            )

        payload = {
            "title": plan.notification_title,
            "message": plan.format_diff(diff),
            "diffItems": diff,
            "diffCount": len(diff),
        }
        delivery_specs = [
            {"channel": target.channel, "destinationKey": target.destination_key}
            for target in self._dispatcher.targets
        ]
        event_id, delivery_ids = self._outbox.create_event_and_deliveries(
            run_id=run_id,
            source_key=plan.source_key,
            source_type=plan.source_type or plan.short_name.lower(),
            payload=payload,
            diff_count=len(diff),
            deliveries=delivery_specs,
            dedupe_key=_dedupe_key(plan.source_key, diff),
        )
        # Snapshot advances once event+deliveries are durably recorded.
        self._snapshots.save(plan.source_key, plan.source_type, plan.target_label or plan.label, items)

        notification_error = self._dispatch_delivery_ids(event_id, delivery_ids, payload)
        return SourceRunResult(
            plan=plan,
            had_data=True,
            diff_count=len(diff),
            notification_error=notification_error,
            saved_history=True,
        )

    def _try_direct_dispatch(self, title: str, message: str) -> str | None:
        errors: list[str] = []
        for target in self._dispatcher.targets:
            try:
                self._dispatcher.send(target.channel, title, message)
            except Exception as e:
                errors.append(f"{target.channel}: {e}")
        return "; ".join(errors) if errors else None

    def _dispatch_delivery_ids(self, event_id: str, delivery_ids: list[str], payload: dict) -> str | None:
        errors: list[str] = []
        retryable = {d["id"]: d for d in self._outbox.list_retryable_deliveries(_iso(_utcnow()), limit=500)}
        for delivery_id in delivery_ids:
            delivery = retryable.get(delivery_id)
            if not delivery:
                continue
            err = self._dispatch_delivery(delivery, payload)
            if err:
                errors.append(err)
        self._outbox.update_event_status(event_id)
        return "; ".join(errors) if errors else None

    def _dispatch_delivery(self, delivery: dict, payload: dict) -> str | None:
        channel = str(delivery.get("channel", ""))
        try:
            self._dispatcher.send(channel, str(payload["title"]), str(payload["message"]))
            event_id = self._outbox.mark_delivery_sent(str(delivery["id"]))
            if event_id:
                self._outbox.update_event_status(event_id)
            return None
        except Exception as e:
            current_attempt_count = int(delivery.get("attemptCount", 0)) + 1
            next_retry = _next_retry_at_iso(
                current_attempt_count=current_attempt_count,
                retry_policy=self._retry_policy,
            )
            event_id = self._outbox.mark_delivery_failed(
                str(delivery["id"]),
                error_message=str(e),
                next_retry_at_iso=next_retry,
            )
            if event_id:
                self._outbox.update_event_status(event_id)
            return f"{channel}: {e}"

    def _process_redeliveries(self) -> tuple[int, int]:
        now_iso = _iso(_utcnow())
        deliveries = self._outbox.list_retryable_deliveries(now_iso, limit=100)
        processed = 0
        failed = 0
        for delivery in deliveries:
            event_id = str(delivery.get("eventId", ""))
            payload = self._outbox.get_event_payload(event_id).get("payload", {})
            if not payload:
                continue
            processed += 1
            if self._dispatch_delivery(delivery, payload) is not None:
                failed += 1
        return processed, failed

