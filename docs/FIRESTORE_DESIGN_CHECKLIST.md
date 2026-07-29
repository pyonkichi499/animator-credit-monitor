# Firestore 設計判断と実装状況

この文書は、現在の Firestore 実装で採用している判断と、未実装の項目を記録します。

## 1. 配送保証

- 採用: `at-least-once`
- 通知取りこぼしを避ける
- 配送重複は発生し得る
- exactly-once は保証しない

`events.dedupeKey` は保存していますが、現在は既存eventの検索や一意性制約には使用していません。

## 2. Snapshot更新

### Firestore

- 差分あり: `events + deliveries` の batch 保存成功後に snapshot を更新
- 差分なし: 非dry-runなら取得結果を保存
- 取得結果が空: snapshot を維持
- 通知失敗: snapshot は戻さず、delivery を次回再送

### local

- 通知成功時だけ履歴JSONを更新
- 通知失敗時は更新せず、次回同じ差分を再検知

## 3. 部分失敗

- run status: `partial_failure`
- 監視処理は可能な範囲で継続
- CLI / GitHub Actions: 非0終了
- 失敗したdeliveryは次回runで再送

## 4. Retry / Redelivery

- 同一実行内リトライ: 有効
- デフォルト再試行: 2回（合計3試行）
- 初期遅延: 60秒
- backoff multiplier: 2
- 次回run再送: 有効
- 1 run の再送取得上限: 100件

未実装:

- `maxAttempts` に達したdeliveryの停止
- dead-letter collection
- 手動再送CLI

## 5. Collections

### `snapshots`

- 監視対象ごとの全取得結果
- TTLなし
- `lastSnapshotHash` を保存するが差分計算には未使用

### `runs`

- 実行開始/終了、status、summary、errors
- `running` / `success` / `partial_failure` / `failed`
- `expiresAt` で30日TTLを想定

### `events`

- 検知差分と通知payload
- `pending` / `sent` / `partially_sent` / `failed`
- 30日TTLを想定

### `deliveries`

- channelごとの配送状態
- 現在のchannelは `console` / `email`
- `pending` / `failed` / `sent`
- 30日TTLを想定

## 6. 実行基盤

- 現在: GitHub Actions
- 認証: GitHub OIDC + WIF
- 状態: Firestore
- 通知: console / SMTP email
- Secrets: GitHub Actions Secrets
- 非秘匿設定: GitHub Actions Variables

## 7. 同時実行

- 排他制御は未実装
- schedule と manual run が重なる可能性あり
- 同じdiffのeventが重複作成される可能性あり

## 8. 保持期間

- `snapshots`: 無期限
- `runs`: 30日
- `events`: 30日
- `deliveries`: 30日

TTL削除はアプリではなく Firestore TTL policy に依存します。

## 9. 将来候補

- concurrent-run locking
- `maxAttempts` の強制
- dead-letter / 運用用再送
- Slack / Discord / generic webhook
- Secret Manager
- Cloud Run Job
- BigQuery / dashboard

いずれも現時点では未実装です。
