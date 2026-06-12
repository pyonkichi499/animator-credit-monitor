# Firestore Runtime Design (GitHub Actions Phase 1)

対象:
- 実行基盤: GitHub Actions
- 状態保存: Firestore
- 認証: GitHub OIDC + Workload Identity Federation (WIF)

方針:
- 配送保証: `at-least-once`
- 部分失敗 (`partial_failure`) は Firestore に記録しつつ GitHub Actions は `exit code != 0`
- `snapshots` は「比較基準」
- `snapshots` 更新条件は `events + deliveries` 永続化成功時

---

## Collections

### `snapshots` (TTLなし)

目的:
- 差分検知の比較基準（前回取得結果）

ドキュメントID例:
- `bangumi_12345`
- `anilist_山田太郎`

主要フィールド:
- `sourceType`
- `sourceKey`
- `targetLabel`
- `lastSnapshot` (array)
- `lastSnapshotHash`
- `lastCheckedAt`
- `updatedAt`

### `runs` (TTL 30日)

目的:
- 実行履歴サマリー

主要フィールド:
- `startedAt`
- `finishedAt`
- `status` (`running` / `success` / `partial_failure`)
- `runtime` (`github_actions`)
- `triggerType` (`schedule` / `manual`)
- `dryRun`
- `summary`
- `errors`
- `expiresAt`

### `events` (TTL 30日)

目的:
- 検知イベント（Outbox親）

主要フィールド:
- `runId`
- `sourceKey`
- `sourceType`
- `eventType` (`new_credits_detected`)
- `payload` (`title`, `message`, `diffItems`, `diffCount`)
- `diffCount`
- `status` (`pending` / `partially_sent` / `sent` / `failed`)
- `dedupeKey`
- `createdAt`
- `updatedAt`
- `expiresAt`

### `deliveries` (TTL 30日)

目的:
- 通知先ごとの配送状態（再送対象）

主要フィールド:
- `eventId`
- `runId`
- `channel` (`email` / `line` / `console`)
- `destinationKey`
- `status` (`pending` / `failed` / `sent`)
- `attemptCount`
- `maxAttempts`
- `nextRetryAt`
- `lastErrorMessage`
- `createdAt`
- `updatedAt`
- `expiresAt`

---

## Execution Flow

1. `runs` を `running` で作成
2. `deliveries` の `pending/failed` で `nextRetryAt <= now` を再送（持ち越し再送）
3. 各 source を取得し diff 判定
4. diff があれば `events + deliveries` を作成（Outbox化）
5. 4 が成功したら `snapshots` を更新
6. 新規 `deliveries` を即時配送（in-run retryあり）
7. `events.status` を `deliveries` から集約更新
8. `runs` を `success` または `partial_failure` で終了

---

## Retry Policy

初期値:
- `NOTIFY_RETRY_MAX_RETRIES=2`
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

挙動:
- 同一実行内リトライ: 60s -> 120s （合計3試行）
- 失敗時は `deliveries.nextRetryAt` を指数バックオフで更新し、次回実行で再送

---

## Exit Code Policy (GitHub Actions)

- `0`: 完全成功
- `非0`: `partial_failure` を含むエラーあり

補足:
- `partial_failure` でも `runs.status` と `deliveries` に状態が保存されるため、次回実行で再送可能

