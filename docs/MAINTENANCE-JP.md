# メンテナンスガイド

## データソース

### Bangumi (`BangumiScraper`)

`src/animator_credit_monitor/scraper.py` は次の HTML 構造に依存します。

| セレクタ | 用途 |
|---|---|
| `ul.browserFull` | 作品リスト |
| `li.item` | 作品エントリ |
| `li[id]` | `item_{ID}` から作品IDを取得 |
| `div.inner > h3 > a.l` | 中国語タイトル |
| `div.inner > h3 > small` | 日本語タイトル（なければ中国語へフォールバック） |
| `div.inner > p.info` | 日付・スタジオ等の情報 |
| `div.inner > span.badge_job` | 役職 |
| `div.page_inner > span.p_edge` | `(current / total)` 形式のページ情報 |

ページ間隔は `request_interval=2.0` 秒がデフォルトです。最初のリクエスト前には待機しません。

Bangumi のレスポンスに charset がない場合へ対応するため、`resp.apparent_encoding` を使用しています。

### AniList (`AniListScraper`)

AniList GraphQL API の `Staff(search:)` と `staffMedia(sort: START_DATE_DESC, perPage: 25)` を使用します。

| APIフィールド | 出力 |
|---|---|
| `node.id` | `id` |
| `node.title.native` | `title`（優先） |
| `node.title.romaji` | `title_romaji` / native がない場合の `title` |
| `staffRole` | `role` |
| `node.startDate` | `date` (`YYYY-MM`) |

代表的な作画役職は日本語へ変換し、未知の役職は原文を維持します。ページネーションは未実装のため最大25件です。

## local 状態管理

履歴ファイル:

```text
data/bangumi_{person_id}_history.json
data/anilist_{target_name}_history.json
```

保存は一時ファイル作成後の `replace` で行います。

### リセット

全ソース:

```bash
rm data/*.json
```

Bangumi のみ:

```bash
rm data/bangumi_*_history.json
```

AniList のみ:

```bash
rm data/anilist_*_history.json
```

次回取得時、削除したソースの全件が新規として扱われます。email を設定している場合は全件通知になるため注意してください。

## Firestore 状態管理

コレクション:

- `snapshots`: 比較基準。TTLなし
- `runs`: 実行監査。`expiresAt` で30日TTLを推奨
- `events`: 検知イベント。30日TTLを推奨
- `deliveries`: 配送状態と再送。30日TTLを推奨

`FIRESTORE_COLLECTION_PREFIX=dev` の場合、`dev_snapshots` のような名前になります。

状態を初期化する場合は、対象の snapshot を削除すると次回の全件が差分になります。`events` / `deliveries` を削除すると未配送通知を失う可能性があるため、内容を確認してから操作してください。

## 通知バックエンド

- `ConsoleNotifier`: 標準出力
- `EmailNotifier`: SMTP、STARTTLS、任意の認証、テンプレート対応
- `MultiNotifier`: 全通知先を実行し、失敗を `MultiNotifierError` に集約

現在選択できる設定値は `console` と `email` です。

### 新しい通知バックエンドを追加する場合

1. `Notifier` を実装する
2. `config.py` の許可値と必要設定を追加する
3. `main.py::_build_delivery_targets()` に配線を追加する
4. notifier / config / CLI / delivery のテストを追加する
5. `.env.example`, workflow, README, Automation/Setup 文書を更新する

## Firestore 配送・再送

- 同一実行内: `max_retries + 1` 回試行
- デフォルト: 初回 + 2回再試行、待機 60秒 → 120秒
- run 開始時に `pending` / `failed` かつ `nextRetryAt <= now` の delivery を最大100件再送
- event status は `sent` / `partially_sent` / `failed`

現状、`maxAttempts=50` はドキュメントへ保存しますが、再送停止条件には使用していません。

## コード品質

```bash
uv lock --check
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
uv build
```

## 通知メッセージ

- タイトル: `新しいクレジット (Bangumi|AniList)`
- 先頭行: `検知件数: N`
- 以降: `1. タイトル [役職] (info/date)`
- email テンプレート変数: `{title}`, `{message}`

未知のテンプレート変数は `ValueError` になります。

## 既知の実装上の制約

- AniList は25件まで
- Bangumi は HTML セレクタ変更の影響を受ける
- Firestore の `dedupeKey` は一意性チェックに未使用
- `lastSnapshotHash` は差分計算の高速化には未使用
- `maxAttempts` は再送上限に未使用
- GitHub Actions / Firestore の同時実行排他は未実装
