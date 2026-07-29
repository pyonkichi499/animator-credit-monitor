# Firestore Runtime Design

## 対象

- 状態バックエンド: `STATE_BACKEND=firestore`
- 実行基盤: 主に GitHub Actions
- 認証: Application Default Credentials。GitHub Actions では OIDC + WIF を使用
- 配送保証: `at-least-once`

## Collections

`FIRESTORE_COLLECTION_PREFIX=dev` の場合、以下は `dev_snapshots` のような名前になります。

### `snapshots`

差分比較の基準。TTLなし。

ドキュメントID:

- `bangumi_{person_id}`
- `anilist_{target_name}`

フィールド:

- `sourceType`
- `sourceKey`
- `targetLabel`
- `lastSnapshot`
- `lastSnapshotHash`
- `lastCheckedAt`
- `updatedAt`

`lastSnapshotHash` は保存していますが、現状の差分判定は各要素の JSON シリアライズ比較を使用します。

### `runs`

実行監査。`expiresAt` による30日TTLを想定。

フィールド:

- `startedAt`, `finishedAt`
- `status`: `running` / `success` / `partial_failure` / `failed`
- `runtime`: 現在のCLIは `github_actions` を設定
- `triggerType`: `manual` / `schedule`
- `dryRun`
- `summary`
- `errors`
- `expiresAt`

例外発生時も `finally` で `failed` として終了更新を試みます。

### `events`

検知差分を保持する Outbox 親。30日TTLを想定。

フィールド:

- `runId`
- `sourceKey`, `sourceType`
- `eventType`: `new_credits_detected`
- `payload`: `title`, `message`, `diffItems`, `diffCount`
- `diffCount`
- `status`: `pending` / `sent` / `partially_sent` / `failed`
- `dedupeKey`
- `createdAt`, `updatedAt`, `expiresAt`

`dedupeKey` は source key と diff の SHA-256 です。現在は保存のみで、一意性チェックや既存event検索には使用していません。

### `deliveries`

通知先ごとの配送状態。30日TTLを想定。

フィールド:

- `eventId`, `runId`
- `channel`: `console` / `email`
- `destinationKey`
- `status`: `pending` / `failed` / `sent`
- `attemptCount`
- `maxAttempts`: 現在は `50` を保存するが、上限判定には未使用
- `nextRetryAt`
- `lastErrorMessage`
- `sentAt`（成功後）
- `createdAt`, `updatedAt`, `expiresAt`

## 実行フロー

1. `runs` を `running` で作成
2. 既存の retryable delivery を最大100件取得して再送
3. 各 source を取得
4. 空の取得結果はスキップし、snapshot を維持
5. snapshot と取得結果を比較
6. 差分なしの場合、非dry-runなら snapshot を保存してチェック時刻を更新
7. 差分あり・非dry-runの場合:
   1. event と各deliveryを Firestore batch で保存
   2. batch成功後に snapshot を更新
   3. 新規deliveryを即時送信
   4. delivery結果からevent statusを集約
8. `runs` を `success` / `partial_failure` / `failed` で終了

## Retry

### 同一実行内

- 試行回数: `NOTIFY_RETRY_MAX_RETRIES + 1`
- デフォルト: 初回 + 2回再試行
- 待機: 60秒 → 120秒（倍率2）

### 次回実行

- 対象: `pending` / `failed` かつ `nextRetryAt <= now`
- 1 run あたり最大100件
- 配送失敗時に `attemptCount` を1増加
- `nextRetryAt` は persisted `attemptCount` に基づく指数バックオフ

現状、`maxAttempts` に達したdeliveryを停止する処理や dead-letter collection はありません。TTLで削除されるまで再送対象になり得ます。

## `--dry-run`

Firestore dry-runでも:

- `runs` は作成・終了される
- run開始時の**既存delivery再送は実行され、delivery/event状態を更新し得る**
- 新規差分の event / delivery / snapshot は作成・更新しない
- 新規差分の通知は Outbox を介さず直接送信する

したがって、`--dry-run` は「監視対象の新しい状態を保存しない」オプションであり、Firestore 全体を完全に読み取り専用にするオプションではありません。

## Status / Exit Code

- `success`: 配送失敗なし
- `partial_failure`: 新規配送または再送に失敗あり
- `failed`: 予期しない例外

CLI は `partial_failure` を含むエラー時に非0で終了します。状態は Firestore に残るため、次回runで再送できます。

## TTL型

Firestore TTL対象の `expiresAt` は timezone-aware `datetime` として保存します。その他の時刻フィールドの多くは ISO 8601 文字列です。
