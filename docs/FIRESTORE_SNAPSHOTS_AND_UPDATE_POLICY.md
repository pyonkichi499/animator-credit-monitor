# Firestore `snapshots` の更新方針

## 責務

`snapshots` は監視対象ごとの前回取得結果を保存し、次回の差分比較基準になります。

持たない責務:

- 通知成否
- 再送状態
- 通知先ごとの配送結果

これらは `events` / `deliveries` が担当します。

## ドキュメント単位

- `snapshots/bangumi_{person_id}`
- `snapshots/anilist_{target_name}`

保存内容:

- `sourceType`, `sourceKey`, `targetLabel`
- `lastSnapshot`
- `lastSnapshotHash`
- `lastCheckedAt`, `updatedAt`

`lastSnapshotHash` は監査・将来最適化用に保存します。現在の差分判定では使用していません。

## 現在の更新条件

### 差分なし

非dry-runでは取得結果を保存し、チェック時刻を更新します。

### 差分あり

1. `events` と `deliveries` を Firestore batch で永続化
2. batch成功後に snapshot を更新
3. deliveryを送信

通知が失敗しても snapshot は戻しません。失敗したdeliveryを次回runで再送します。

### 取得結果が空

取得失敗と本当に0件の区別ができないため、snapshot を更新しません。

### dry-run

新規取得結果で snapshot を更新しません。ただし、run開始時の既存delivery再送は別処理として実行されます。

## 部分失敗例

`NOTIFIERS=console,email` で console が成功し email が失敗した場合:

- eventを1件作成
- console / email のdeliveryを作成
- snapshotを更新
- console deliveryは `sent`
- email deliveryは `failed`
- eventは `partially_sent`
- runは `partial_failure` となりCLIは非0終了
- 次回runは失敗したemail deliveryを再送

## local backendとの違い

local backend は Outbox を持ちません。そのため通知に失敗すると履歴JSONを更新せず、次回実行で同じ差分を再検知します。

## 重複について

Firestore eventには `dedupeKey` を保存しますが、現在は既存eventとの照合や一意性制約を実装していません。Outbox と snapshot 更新により通常の再検知は抑えますが、同時実行などでは重複event・通知が発生し得ます。
