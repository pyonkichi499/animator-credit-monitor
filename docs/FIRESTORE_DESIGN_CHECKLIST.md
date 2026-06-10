# Firestore Design Checklist (Answer Sheet)

このファイルに記入して返してください。  
目的: `GitHub Actions + Firestore` 前提で、実装スコープと信頼性要件を確定する。

記入ルール
- `TODO:` を選択肢で置き換える
- 必要なら自由記述を追記
- 未決定は `保留` と書いてOK

---

## 1. 基本方針（最重要）

### 1-1. 配送保証レベル
- [x] `at-least-once`（重複通知はあり得るが、取りこぼしを避ける）
- [ ] `at-most-once`（重複通知を避けるが、取りこぼしの可能性を許容）
- 回答: `at-least-once`
- 補足: 通知先毎に管理して、それぞれ1回ずつ通知できるならしたい。優先度低

### 1-2. 通知失敗時の履歴（snapshot）更新
- [x] 通知成功時のみ `snapshots` を更新する（取りこぼし防止）
- [ ] 通知失敗でも `snapshots` を更新する（重複通知抑制優先）
- 回答: `通知成功時のみ更新（Outbox パターンで実装）`
- 補足: Firestore バックエンドでは Outbox パターンを採用。event + deliveries が Firestore に永続化された時点で snapshot を更新する。通知自体が失敗しても delivery レコードが残り、次回 run で redelivery される。ローカルバックエンドでは通知成功時のみ保存。

### 1-3. 一部通知先失敗時の扱い（email成功 / line失敗 など）
- [ ] `partial_failure` として扱い、実行全体を失敗（非0終了）にする
- [x] `partial_failure` でも実行全体は成功扱いにする
- 回答: `partial_failure は記録するが、run 自体は継続する`
- 補足: run status は `partial_failure` に設定される（redelivery_failed > 0 または notification_error あり）。失敗した delivery は outbox に残り次回 redelivery される。

### 1-4. 重複通知の許容度
- [x] ある程度許容（監視用途なので取りこぼし回避優先）
- [ ] できるだけ避けたい（重複はほぼNG）
- 回答: `ある程度許容`
- 補足: dedupe_key（source_key + diff の SHA-256）で同一差分の重複イベント生成を抑制するが、delivery レベルでは at-least-once のため重複送信の可能性あり。

---

## 2. 再送（Retry / Redelivery）

### 2-1. 同一実行内リトライ（in-run retry）
- [x] 必要（推奨）
- [ ] 不要
- 回答: `必要`

### 2-2. 同一実行内リトライ回数（初期値）
- [ ] 0回（再試行なし）
- [ ] 1回
- [x] 2回
- [ ] 3回
- [ ] その他:
- 回答: `2回`（`NOTIFY_RETRY_MAX_RETRIES` 環境変数で変更可能、デフォルト2）

### 2-3. 次回実行での持ち越し再送（cross-run retry / Outbox）
- [x] Phase 1 から必要
- [ ] Phase 2 で追加（最初は不要）
- [ ] 不要
- 回答: `Phase 1 から実装済み`
- 補足: 各 run 開始時に `_process_redeliveries()` で `next_retry_at` を過ぎた failed delivery を自動再送。指数バックオフ（初期60秒、倍率2x）で next_retry_at を計算。

### 2-4. 再送対象
- [x] 通知失敗したものだけ再送したい
- [ ] 再実行で同じ差分を再検知できれば十分（専用再送は不要）
- 回答: `通知失敗したものだけ再送`

---

## 3. Firestore 保存設計（Phase 1 スコープ）

### 3-1. Phase 1 で実装するコレクション
- [ ] `snapshots` + `runs` のみ（推奨）
- [x] `snapshots` + `runs` + `events` + `deliveries` まで一気に
- 回答: `snapshots + runs + events + deliveries`（全て実装済み）

### 3-2. `runs` に保存する情報の粒度
- [x] サマリー中心（件数・状態・エラー概要）
- [ ] 詳細ログも保存（sourceごとの詳細を多めに）
- 回答: `サマリー中心`
- 補足: startedAt, finishedAt, status, runtime, triggerType, dryRun, summary (dict), errors (list)。TTL 30日。

### 3-3. `snapshots` に保存する内容
- [x] 取得結果の全件（現在と同等）
- [ ] 最小限（差分判定に必要なキーのみ）
- 回答: `取得結果の全件`
- 補足: lastSnapshot に全件保存 + SHA-256 ハッシュ（lastSnapshotHash）で差分検出を高速化。TTL なし（永続保持）。

---

## 4. 保持期間 / 運用

### 4-1. `runs` の保持期間
- [x] 30日
- [ ] 90日（推奨）
- [ ] 180日
- [ ] 無期限
- [ ] その他:
- 回答: `30日`（`_ttl_after()` で expiresAt を設定、Firestore TTL ポリシーで自動削除）

### 4-2. `events` / `deliveries` の保持期間（Phase 2 時）
- [x] 30日
- [ ] 60日（推奨）
- [ ] 90日
- [ ] 無期限
- [ ] 未定
- 回答: `30日`（runs と同じ TTL 設定で実装済み）

### 4-3. 手動実行と定期実行の同時実行（将来含む）
- [x] 当面は気にしない（重複実行の可能性を許容）
- [ ] 排他制御を Phase 1 から入れたい
- [ ] 排他制御を Phase 2 で入れる
- 回答: `当面は気にしない`

---

## 5. 実行基盤 / シークレット / 予算

### 5-1. 当面の実行基盤
- [x] GitHub Actions（推奨）
- [ ] Cloud Run Job（今すぐ移行）
- [ ] その他:
- 回答: `GitHub Actions`

### 5-2. シークレット管理（当面）
- [x] GitHub Actions Secrets（推奨）
- [ ] GCP Secret Manager（今すぐ移行）
- [ ] その他:
- 回答: `GitHub Actions Secrets + Variables`
- 補足: 実行基盤を Cloud Run に移行するタイミングで、シークレットも Secret Manager に移行したい。非秘匿値は GitHub Variables で管理。

### 5-3. 月額予算感（ざっくり）
- [x] ほぼ無料優先（~$0-5）
- [ ] 低コストならOK（~$5-15）
- [ ] ある程度かけてもOK（~$15-50）
- [ ] 未定
- 回答: `ほぼ無料優先（~$0-5）`

---

## 6. 将来要件（今は設計だけ反映するか）

### 6-1. 監視対象数の想定（将来）
- [x] 1対象のみ
- [ ] 数件（2-10件）
- [ ] 10件以上の可能性あり
- 回答: `1対象のみ`

### 6-2. 通知先の将来拡張
- [x] Email / LINE だけで十分
- [ ] Slack / Discord / Webhook を追加したい可能性あり
- 回答: `Email / LINE だけで十分`

### 6-3. 運用画面 / 分析の必要性
- [ ] 不要（ログ確認だけで十分）
- [ ] 実行履歴の見える化がほしい（簡易）
- [x] 将来 BigQuery / ダッシュボードも視野
- 回答: `将来 BigQuery / ダッシュボードも視野`

---

## 7. 最終確認（この回答で実装を進めてよいか）

- [x] 上記回答を前提に実装を進めてOK
- [ ] 実装前に追加で設計レビューしたい
- 回答: `実装済み（Phase 1 完了、全項目の方針に基づいて実装が完了している）`

補足・自由記述:
- Phase 1 の全コレクション（snapshots / runs / events / deliveries）が実装済み
- Outbox パターンによる at-least-once 配信が動作中
- テスト 106件で全レイヤーをカバー（pytest / ruff / mypy 全グリーン）
- Dead-letter 機構は未実装（failed delivery は TTL 30日で自然消滅）
