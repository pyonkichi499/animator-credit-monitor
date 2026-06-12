from unittest.mock import MagicMock, patch

from animator_credit_monitor.firestore_store import (
    FirestoreCollections,
    FirestoreOutboxRepository,
    FirestoreRunRepository,
    FirestoreSnapshotRepository,
    build_collections,
)

# ---- helpers ----


def _mock_client() -> MagicMock:
    """Firestore クライアントのモックを生成する。"""
    return MagicMock()


def _mock_doc(*, exists: bool = True, data: dict | None = None, doc_id: str = "doc1") -> MagicMock:
    """Firestore ドキュメントスナップショットのモックを生成する。"""
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data if data is not None else {}
    doc.id = doc_id
    return doc


def _collections() -> FirestoreCollections:
    return build_collections("")


# ---- build_collections ----


def test_build_collectionsはプレフィックスなしでデフォルト名を返す() -> None:
    cols = build_collections("")
    assert cols.snapshots == "snapshots"
    assert cols.runs == "runs"
    assert cols.events == "events"
    assert cols.deliveries == "deliveries"


def test_build_collectionsはプレフィックス付きで名前を結合する() -> None:
    cols = build_collections("test")
    assert cols.snapshots == "test_snapshots"
    assert cols.runs == "test_runs"
    assert cols.events == "test_events"
    assert cols.deliveries == "test_deliveries"


def test_build_collectionsは空白のみのプレフィックスを無視する() -> None:
    cols = build_collections("  ")
    assert cols.snapshots == "snapshots"


# ---- FirestoreSnapshotRepository ----


class TestFirestoreSnapshotRepository:
    def test_loadはドキュメントが存在しない場合に空リストを返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=False)
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        result = repo.load("source1")

        assert result == []
        client.collection.assert_called_with("snapshots")

    def test_loadはlastSnapshotをリストとして返す(self) -> None:
        client = _mock_client()
        items = [{"id": "1", "title": "作品A"}]
        doc = _mock_doc(exists=True, data={"lastSnapshot": items})
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        result = repo.load("source1")

        assert result == items

    def test_loadはlastSnapshotがリストでない場合に空リストを返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"lastSnapshot": "not_a_list"})
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        result = repo.load("source1")

        assert result == []

    def test_detect_diffは旧データがない場合に全件を差分として返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=False)
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        new_data = [{"id": "1"}, {"id": "2"}]
        result = repo.detect_diff("source1", new_data)

        assert result == new_data

    def test_detect_diffは差分のあるアイテムのみ返す(self) -> None:
        client = _mock_client()
        old_items = [{"id": "1", "title": "A"}]
        doc = _mock_doc(exists=True, data={"lastSnapshot": old_items})
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        new_data = [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}]
        result = repo.detect_diff("source1", new_data)

        assert len(result) == 1
        assert result[0]["id"] == "2"

    def test_detect_diffは差分がない場合に空リストを返す(self) -> None:
        client = _mock_client()
        items = [{"id": "1"}]
        doc = _mock_doc(exists=True, data={"lastSnapshot": items})
        client.collection.return_value.document.return_value.get.return_value = doc

        repo = FirestoreSnapshotRepository(client, _collections())
        result = repo.detect_diff("source1", [{"id": "1"}])

        assert result == []

    def test_saveはスナップショットをFirestoreに保存する(self) -> None:
        client = _mock_client()
        repo = FirestoreSnapshotRepository(client, _collections())
        data = [{"id": "1", "title": "作品A"}]

        repo.save("source1", "bangumi", "テスト対象", data)

        set_call = client.collection.return_value.document.return_value.set
        set_call.assert_called_once()
        saved = set_call.call_args[0][0]
        assert saved["sourceType"] == "bangumi"
        assert saved["sourceKey"] == "source1"
        assert saved["targetLabel"] == "テスト対象"
        assert saved["lastSnapshot"] == data
        assert saved["lastSnapshotHash"].startswith("sha256:")


# ---- FirestoreRunRepository ----


class TestFirestoreRunRepository:
    @patch("animator_credit_monitor.firestore_store.uuid.uuid4", return_value="test-run-id")
    def test_start_runはrun_idを返してドキュメントを作成する(self, _mock_uuid: MagicMock) -> None:
        client = _mock_client()
        repo = FirestoreRunRepository(client, _collections())

        run_id = repo.start_run(runtime="github-actions", trigger_type="schedule", dry_run=False)

        assert run_id == "test-run-id"
        set_call = client.collection.return_value.document.return_value.set
        set_call.assert_called_once()
        saved = set_call.call_args[0][0]
        assert saved["status"] == "running"
        assert saved["runtime"] == "github-actions"
        assert saved["triggerType"] == "schedule"
        assert saved["dryRun"] is False
        assert saved["finishedAt"] is None
        assert "expiresAt" in saved

    def test_finish_runはステータスとサマリーを更新する(self) -> None:
        client = _mock_client()
        repo = FirestoreRunRepository(client, _collections())
        summary = {"checksRun": 2}
        errors = ["error1"]

        repo.finish_run("run-123", status="success", summary=summary, errors=errors)

        update_call = client.collection.return_value.document.return_value.update
        update_call.assert_called_once()
        updated = update_call.call_args[0][0]
        assert updated["status"] == "success"
        assert updated["summary"] == summary
        assert updated["errors"] == errors
        assert updated["finishedAt"] is not None


# ---- FirestoreOutboxRepository ----


class TestFirestoreOutboxRepository:
    @patch("animator_credit_monitor.firestore_store.uuid.uuid4", side_effect=["ev-1", "dl-1", "dl-2"])
    def test_create_event_and_deliveriesはバッチ書き込みでイベントと配信を作成する(
        self, _mock_uuid: MagicMock
    ) -> None:
        client = _mock_client()
        batch = MagicMock()
        client.batch.return_value = batch
        repo = FirestoreOutboxRepository(client, _collections())

        event_id, delivery_ids = repo.create_event_and_deliveries(
            run_id="run-1",
            source_key="src-1",
            source_type="bangumi",
            payload={"title": "test"},
            diff_count=3,
            deliveries=[
                {"channel": "email", "destinationKey": "user@example.com"},
                {"channel": "line", "destinationKey": "token123"},
            ],
            dedupe_key="dedup-1",
        )

        assert event_id == "ev-1"
        assert delivery_ids == ["dl-1", "dl-2"]
        # batch.set は3回呼ばれる (1 event + 2 deliveries)
        assert batch.set.call_count == 3
        batch.commit.assert_called_once()

    def test_list_retryable_deliveriesはidフィールドを付与して返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"status": "pending", "channel": "email"}, doc_id="dlv-1")
        query = MagicMock()
        query.where.return_value = query
        query.limit.return_value = query
        query.stream.return_value = [doc]
        client.collection.return_value = query
        repo = FirestoreOutboxRepository(client, _collections())

        result = repo.list_retryable_deliveries("2026-01-01T00:00:00+00:00", limit=10)

        assert len(result) == 1
        assert result[0]["id"] == "dlv-1"
        assert result[0]["channel"] == "email"

    def test_get_deliveryはドキュメントが存在する場合にidを付与して返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"channel": "line", "eventId": "ev-1"}, doc_id="dlv-1")
        client.collection.return_value.document.return_value.get.return_value = doc
        repo = FirestoreOutboxRepository(client, _collections())

        result = repo.get_delivery("dlv-1")

        assert result is not None
        assert result["id"] == "dlv-1"
        assert result["channel"] == "line"

    def test_get_deliveryはドキュメントが存在しない場合にNoneを返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=False)
        client.collection.return_value.document.return_value.get.return_value = doc
        repo = FirestoreOutboxRepository(client, _collections())

        result = repo.get_delivery("dlv-999")

        assert result is None

    def test_mark_delivery_sentはステータスを更新してeventIdを返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"attemptCount": 1, "eventId": "ev-1"})
        ref = MagicMock()
        ref.get.return_value = doc
        client.collection.return_value.document.return_value = ref
        repo = FirestoreOutboxRepository(client, _collections())

        event_id = repo.mark_delivery_sent("dlv-1")

        assert event_id == "ev-1"
        updated = ref.update.call_args[0][0]
        assert updated["status"] == "sent"
        assert updated["attemptCount"] == 2
        assert updated["lastErrorMessage"] is None

    def test_mark_delivery_failedはエラーメッセージとリトライ時刻を記録する(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"attemptCount": 0, "eventId": "ev-2"})
        ref = MagicMock()
        ref.get.return_value = doc
        client.collection.return_value.document.return_value = ref
        repo = FirestoreOutboxRepository(client, _collections())

        event_id = repo.mark_delivery_failed(
            "dlv-1", error_message="connection refused", next_retry_at_iso="2026-01-02T00:00:00+00:00"
        )

        assert event_id == "ev-2"
        updated = ref.update.call_args[0][0]
        assert updated["status"] == "failed"
        assert updated["attemptCount"] == 1
        assert updated["lastErrorMessage"] == "connection refused"
        assert updated["nextRetryAt"] == "2026-01-02T00:00:00+00:00"

    def test_mark_delivery_failedはエラーメッセージを1000文字で切り詰める(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=True, data={"attemptCount": 0, "eventId": "ev-3"})
        ref = MagicMock()
        ref.get.return_value = doc
        client.collection.return_value.document.return_value = ref
        repo = FirestoreOutboxRepository(client, _collections())

        long_error = "x" * 2000
        repo.mark_delivery_failed("dlv-1", error_message=long_error, next_retry_at_iso="2026-01-02T00:00:00+00:00")

        updated = ref.update.call_args[0][0]
        assert len(updated["lastErrorMessage"]) == 1000

    def test_get_event_payloadはドキュメントが存在しない場合に空辞書を返す(self) -> None:
        client = _mock_client()
        doc = _mock_doc(exists=False)
        client.collection.return_value.document.return_value.get.return_value = doc
        repo = FirestoreOutboxRepository(client, _collections())

        result = repo.get_event_payload("ev-999")

        assert result == {}

    def test_get_event_payloadはドキュメントの内容を返す(self) -> None:
        client = _mock_client()
        payload = {"title": "test", "message": "msg"}
        doc = _mock_doc(exists=True, data={"payload": payload, "status": "pending"})
        client.collection.return_value.document.return_value.get.return_value = doc
        repo = FirestoreOutboxRepository(client, _collections())

        result = repo.get_event_payload("ev-1")

        assert result["payload"] == payload

    def test_update_event_statusは全配信sentの場合にsentを返す(self) -> None:
        client = _mock_client()
        docs = [
            _mock_doc(data={"status": "sent"}, doc_id="d1"),
            _mock_doc(data={"status": "sent"}, doc_id="d2"),
        ]
        query = MagicMock()
        query.where.return_value = query
        query.stream.return_value = docs
        # collection calls: first for deliveries (query), then for events (update)
        event_ref = MagicMock()
        client.collection.side_effect = [query, MagicMock(document=MagicMock(return_value=event_ref))]
        repo = FirestoreOutboxRepository(client, _collections())

        status = repo.update_event_status("ev-1")

        assert status == "sent"

    def test_update_event_statusは一部sentの場合にpartially_sentを返す(self) -> None:
        client = _mock_client()
        docs = [
            _mock_doc(data={"status": "sent"}, doc_id="d1"),
            _mock_doc(data={"status": "failed"}, doc_id="d2"),
        ]
        query = MagicMock()
        query.where.return_value = query
        query.stream.return_value = docs
        event_ref = MagicMock()
        client.collection.side_effect = [query, MagicMock(document=MagicMock(return_value=event_ref))]
        repo = FirestoreOutboxRepository(client, _collections())

        status = repo.update_event_status("ev-1")

        assert status == "partially_sent"

    def test_update_event_statusは配信がない場合にfailedを返す(self) -> None:
        client = _mock_client()
        query = MagicMock()
        query.where.return_value = query
        query.stream.return_value = []
        event_ref = MagicMock()
        client.collection.side_effect = [query, MagicMock(document=MagicMock(return_value=event_ref))]
        repo = FirestoreOutboxRepository(client, _collections())

        status = repo.update_event_status("ev-1")

        assert status == "failed"
