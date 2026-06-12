import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _ttl_after(days: int) -> datetime:
    return _utcnow() + timedelta(days=days)


def _serialize_for_diff(item: dict | list[dict]) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class FirestoreCollections:
    snapshots: str
    runs: str
    events: str
    deliveries: str


def build_collections(prefix: str) -> FirestoreCollections:
    p = f"{prefix.strip()}_" if prefix.strip() else ""
    return FirestoreCollections(
        snapshots=f"{p}snapshots",
        runs=f"{p}runs",
        events=f"{p}events",
        deliveries=f"{p}deliveries",
    )


class FirestoreDependencyError(RuntimeError):
    pass


def create_firestore_client(project_id: str, database: str) -> Any:
    try:
        from google.cloud import firestore  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover
        raise FirestoreDependencyError(
            "google-cloud-firestore is required when STATE_BACKEND=firestore"
        ) from e

    return firestore.Client(project=project_id, database=database)


class FirestoreSnapshotRepository:
    def __init__(self, client: Any, collections: FirestoreCollections) -> None:
        self._client = client
        self._col = collections.snapshots

    def load(self, source_key: str) -> list[dict]:
        doc = self._client.collection(self._col).document(source_key).get()
        if not doc.exists:
            return []
        data = doc.to_dict() or {}
        last_snapshot = data.get("lastSnapshot", [])
        return last_snapshot if isinstance(last_snapshot, list) else []

    def detect_diff(self, source_key: str, new_data: list[dict]) -> list[dict]:
        old_data = self.load(source_key)
        if not old_data:
            return new_data
        old_set = {_serialize_for_diff(item) for item in old_data}
        return [item for item in new_data if _serialize_for_diff(item) not in old_set]

    def save(self, source_key: str, source_type: str, target_label: str, data: list[dict]) -> None:
        now = _iso_now()
        snapshot_hash = f"sha256:{sha256(_serialize_for_diff(data).encode('utf-8')).hexdigest()}"
        self._client.collection(self._col).document(source_key).set(
            {
                "sourceType": source_type,
                "sourceKey": source_key,
                "targetLabel": target_label,
                "lastSnapshot": data,
                "lastSnapshotHash": snapshot_hash,
                "lastCheckedAt": now,
                "updatedAt": now,
            }
        )


class FirestoreRunRepository:
    def __init__(self, client: Any, collections: FirestoreCollections, ttl_days: int = 30) -> None:
        self._client = client
        self._col = collections.runs
        self._ttl_days = ttl_days

    def start_run(self, *, runtime: str, trigger_type: str, dry_run: bool) -> str:
        run_id = str(uuid.uuid4())
        self._client.collection(self._col).document(run_id).set(
            {
                "startedAt": _iso_now(),
                "finishedAt": None,
                "status": "running",
                "runtime": runtime,
                "triggerType": trigger_type,
                "dryRun": dry_run,
                "summary": {},
                "errors": [],
                "expiresAt": _ttl_after(self._ttl_days),
            }
        )
        return run_id

    def finish_run(self, run_id: str, *, status: str, summary: dict[str, Any], errors: list[str]) -> None:
        self._client.collection(self._col).document(run_id).update(
            {
                "finishedAt": _iso_now(),
                "status": status,
                "summary": summary,
                "errors": errors,
                "expiresAt": _ttl_after(self._ttl_days),
            }
        )


class FirestoreOutboxRepository:
    def __init__(self, client: Any, collections: FirestoreCollections, ttl_days: int = 30) -> None:
        self._client = client
        self._events_col = collections.events
        self._deliveries_col = collections.deliveries
        self._ttl_days = ttl_days

    def create_event_and_deliveries(
        self,
        *,
        run_id: str,
        source_key: str,
        source_type: str,
        payload: dict[str, Any],
        diff_count: int,
        deliveries: list[dict[str, str]],
        dedupe_key: str,
    ) -> tuple[str, list[str]]:
        event_id = str(uuid.uuid4())
        now = _iso_now()
        batch = self._client.batch()

        event_ref = self._client.collection(self._events_col).document(event_id)
        batch.set(
            event_ref,
            {
                "runId": run_id,
                "sourceKey": source_key,
                "sourceType": source_type,
                "eventType": "new_credits_detected",
                "payload": payload,
                "diffCount": diff_count,
                "status": "pending",
                "dedupeKey": dedupe_key,
                "createdAt": now,
                "updatedAt": now,
                "expiresAt": _ttl_after(self._ttl_days),
            },
        )

        delivery_ids: list[str] = []
        for delivery in deliveries:
            delivery_id = str(uuid.uuid4())
            delivery_ids.append(delivery_id)
            delivery_ref = self._client.collection(self._deliveries_col).document(delivery_id)
            batch.set(
                delivery_ref,
                {
                    "eventId": event_id,
                    "runId": run_id,
                    "channel": delivery["channel"],
                    "destinationKey": delivery["destinationKey"],
                    "status": "pending",
                    "attemptCount": 0,
                    "maxAttempts": 50,
                    "nextRetryAt": now,
                    "lastErrorMessage": None,
                    "createdAt": now,
                    "updatedAt": now,
                    "expiresAt": _ttl_after(self._ttl_days),
                },
            )
        batch.commit()
        return event_id, delivery_ids

    def list_retryable_deliveries(self, now_iso: str, *, limit: int = 100) -> list[dict[str, Any]]:
        docs = (
            self._client.collection(self._deliveries_col)
            .where("status", "in", ["pending", "failed"])
            .where("nextRetryAt", "<=", now_iso)
            .limit(limit)
            .stream()
        )
        results: list[dict[str, Any]] = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            results.append(data)
        return results

    def get_delivery(self, delivery_id: str) -> dict[str, Any] | None:
        doc = self._client.collection(self._deliveries_col).document(delivery_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        data["id"] = doc.id
        return data

    def mark_delivery_sent(self, delivery_id: str) -> str:
        now = _iso_now()
        ref = self._client.collection(self._deliveries_col).document(delivery_id)
        snap = ref.get()
        data = snap.to_dict() or {}
        ref.update(
            {
                "status": "sent",
                "attemptCount": int(data.get("attemptCount", 0)) + 1,
                "sentAt": now,
                "lastErrorMessage": None,
                "updatedAt": now,
                "expiresAt": _ttl_after(self._ttl_days),
            }
        )
        return str(data.get("eventId", ""))

    def mark_delivery_failed(self, delivery_id: str, *, error_message: str, next_retry_at_iso: str) -> str:
        now = _iso_now()
        ref = self._client.collection(self._deliveries_col).document(delivery_id)
        snap = ref.get()
        data = snap.to_dict() or {}
        ref.update(
            {
                "status": "failed",
                "attemptCount": int(data.get("attemptCount", 0)) + 1,
                "lastErrorMessage": error_message[:1000],
                "nextRetryAt": next_retry_at_iso,
                "updatedAt": now,
                "expiresAt": _ttl_after(self._ttl_days),
            }
        )
        return str(data.get("eventId", ""))

    def get_event_payload(self, event_id: str) -> dict[str, Any]:
        doc = self._client.collection(self._events_col).document(event_id).get()
        if not doc.exists:
            return {}
        return doc.to_dict() or {}

    def update_event_status(self, event_id: str) -> str:
        docs = self._client.collection(self._deliveries_col).where("eventId", "==", event_id).stream()
        statuses = [str((doc.to_dict() or {}).get("status", "")) for doc in docs]
        if not statuses:
            status = "failed"
        elif all(s == "sent" for s in statuses):
            status = "sent"
        elif any(s == "sent" for s in statuses):
            status = "partially_sent"
        elif any(s in {"pending", "failed"} for s in statuses):
            status = "failed"
        else:
            status = "failed"

        self._client.collection(self._events_col).document(event_id).update(
            {
                "status": status,
                "updatedAt": _iso_now(),
                "expiresAt": _ttl_after(self._ttl_days),
            }
        )
        return status
