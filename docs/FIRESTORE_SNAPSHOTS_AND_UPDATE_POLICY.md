# Firestore: `snapshots` の役割と更新タイミング

このメモは、Firestore 前提の設計で `snapshots` の責務と更新条件を整理するためのものです。

---

## 1. `snapshots` とは何か

`snapshots` は、各監視対象の「前回取得した結果（比較基準）」を保存するコレクションです。

目的:
- 次回実行時の差分検知
- 「すでに見たデータ」の基準を保持する

重要:
- `snapshots` は「通知の成否」を管理する場所ではない
- 通知の状態は `events` / `deliveries` で管理する

---

## 2. `snapshots` の責務

`snapshots` が持つ責務:
- 前回取得データの保存（baseline）
- 差分検知の比較元
- 最終チェック時刻の記録

`snapshots` が持たない責務:
- 通知送信の成功/失敗
- 再送管理
- notifier ごとの配送状態

---

## 3. ドキュメント単位（Firestore）

- 1監視対象 = 1ドキュメント
- 例:
  - `snapshots/bangumi_12345`
  - `snapshots/anilist_山田太郎`

---

## 4. 推奨ドキュメント構造（例）

```json
{
  "sourceType": "anilist",
  "sourceKey": "anilist_山田太郎",
  "targetLabel": "山田太郎",
  "lastSnapshot": [
    {
      "id": "123",
      "title": "作品A",
      "role": "原画",
      "date": "2026-02"
    },
    {
      "id": "456",
      "title": "作品B",
      "role": "作画監督",
      "date": "2026-01"
    }
  ],
  "lastSnapshotHash": "sha256:...",
  "lastCheckedAt": "2026-02-23T00:00:00Z",
  "updatedAt": "2026-02-23T00:00:01Z"
}
```

フィールド説明:
- `sourceType`: `bangumi` / `anilist`
- `sourceKey`: 一意キー（例: `bangumi_12345`）
- `targetLabel`: 人が読みやすい表示名（任意）
- `lastSnapshot`: 前回取得した一覧（差分比較の本体）
- `lastSnapshotHash`: ハッシュ（任意、最適化用）
- `lastCheckedAt`: 最後に取得できた時刻
- `updatedAt`: このドキュメントの更新時刻

---

## 5. 更新タイミングの選択肢

### A. 通知成功時のみ `snapshots` を更新する

意味:
- 通知が送れていないデータは「見たことにしない」

メリット:
- 取りこぼし防止の思想として直感的

デメリット（Outbox/再送を入れる場合に大きい）:
- 一部通知先失敗で `snapshots` が進まない
- 次回実行で同じ差分を再検知しやすい
- 同じ `events` が増えやすい（重複イベント）

向いているケース:
- Outbox を使わない
- 再送は「再検知」で十分

---

### B. `events + deliveries` の永続化成功時に `snapshots` を更新する（推奨）

意味:
- 差分を「再送可能なイベントとして保存できた時点」で取りこぼしていないとみなす

メリット:
- `snapshots` は比較基準として進められる
- 通知失敗は `deliveries` の再送で処理できる
- 次回実行で同じ差分を再検知しにくい
- `snapshots`（比較基準）と `deliveries`（配送状態）の責務分離が明確

デメリット:
- 通知未達でも `snapshots` は更新される
- そのため `events/deliveries` の保存失敗は防ぐ必要がある

向いているケース:
- Outbox（`events` / `deliveries`）を使う
- 持ち越し再送をしたい

---

## 6. 具体例（Email成功・LINE失敗）

前提:
- 新着差分 3件検知
- Email 成功
- LINE 失敗

### A. 通知成功時のみ `snapshots` 更新

- `snapshots` は更新されない
- 次回実行でも同じ3件が diff 扱いになりやすい
- Email 側まで重複通知されやすい

### B. `events + deliveries` 作成成功時に `snapshots` 更新

- `events` 1件作成
- `deliveries`（email, line）作成
- `snapshots` 更新
- 次回実行では同じ3件は通常 diff にならない
- LINE 失敗分だけ `deliveries` から再送できる

---

## 7. このプロジェクトでの推奨結論

前提要件:
- `at-least-once`
- 重複通知はある程度許容
- 持ち越し再送を Phase 1 から実施
- Firestore で `events` / `deliveries` まで持つ

この前提なら、`snapshots` は以下として扱うのが最も整合的です。

- `snapshots` = 差分比較の基準
- 更新条件 = `events + deliveries` の永続化成功時

これにより:
- 取りこぼし防止（`events/deliveries` で担保）
- 重複イベント抑制（`snapshots` 更新）
- 部分失敗の再送（`deliveries` で担保）

---

## 8. 責務分担（要約）

- `snapshots`: 差分比較の基準
- `events`: 検知した差分（通知すべき内容）
- `deliveries`: 通知先ごとの配送状態・再送状態
- `runs`: 実行履歴サマリー

