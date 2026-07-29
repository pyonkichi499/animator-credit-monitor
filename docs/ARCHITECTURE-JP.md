# アーキテクチャ

## 概要

Animator Credit Monitor は、次の処理を行う Click ベースの Python CLI です。

1. Bangumi / AniList からクレジット一覧を取得
2. local JSON または Firestore の前回状態と比較
3. 新規クレジットを console / email へ通知
4. 実行結果と次回比較用の状態を保存

## モジュール

| モジュール | 責務 |
|---|---|
| `main.py` | CLI、設定読込、依存構築、source/backend選択、終了コード |
| `config.py` | 環境変数の解析、正規化、検証エラー集約 |
| `scraper.py` | Bangumi HTML / AniList GraphQL の取得と正規化 |
| `formatters.py` | 差分リストから標準通知本文を生成 |
| `notifier.py` | console / SMTP email、local向け複数通知 |
| `delivery.py` | Firestore向け通知targetと同一実行内リトライ |
| `history.py` | local JSONの読込・差分検知・原子的保存 |
| `usecase.py` | local backend の監視フロー |
| `firestore_store.py` | Firestore repositoryとcollection名 |
| `firestore_usecase.py` | Outbox、snapshot更新、再送、run監査 |
| `models.py` | source計画と実行結果の値オブジェクト |
| `ports.py` | local usecaseが依存するProtocol |

## CLI構築

`animator_credit_monitor.main:cli` がエントリポイントです。

1. `.env` を `python-dotenv` で読み込む
2. `load_app_config_from_env()` で全設定を検証
3. CLIオプションと監視対象の組み合わせを検証
4. `STATE_BACKEND` に応じて local / Firestore を選択
5. `TARGET_BANGUMI_ID` / `TARGET_NAME` から `SourcePlan` を構築
6. `RunReport` の内容により終了コードを決定

設定検証は可能な限り複数のエラーをまとめて返します。

## Source Adapter

### Bangumi

- `requests.Session` とブラウザ相当のheaderを使用
- `/person/{id}/works` を取得
- ページ間にデフォルト2秒待機
- 日本語タイトルがない場合は中国語タイトルへフォールバック
- HTTP/接続エラー時は、取得済みページがあれば部分結果、なければ空リスト

### AniList

- `POST https://graphql.anilist.co`
- `Staff(search:)` で名前検索
- `staffMedia(sort: START_DATE_DESC, perPage: 25)`
- native titleを優先し、なければromaji title
- 作画関連の代表的なroleを日本語化
- HTTP/接続エラー、staff未検出時は空リスト

空リストは「取得失敗」と「本当に0件」を区別できないため、どちらのbackendも既存の比較基準を更新しません。

## local Backend

```text
fetch
  → emptyならskip
  → HistoryManager.detect_diff
  → diffありならNotifier.notify
  → 通知成功かつ非dry-runならHistoryManager.save
  → RunReport
```

特徴:

- 履歴単位: `source_key`
- ファイル: `DATA_DIR/{source_key}_history.json`
- 初回: 全件を差分扱い
- 差分なしでも非dry-runなら最新取得結果を保存
- 通知失敗時は履歴を進めない
- 複数通知先は `MultiNotifier` が全通知先を試し、失敗を集約

## Firestore Backend

```text
start run
  → retryable deliveriesを再送
  → sourceごとにfetch/diff
      → diffなし: snapshot更新
      → dry-run: 直接通知
      → diffあり: event+deliveriesをbatch保存
                    → snapshot更新
                    → delivery送信
                    → event status集約
  → finish run
  → RunReport
```

### Outbox

- event と delivery は同じ Firestore batch で作成
- batch成功後に snapshot を更新
- 通知失敗時は deliveryを `failed` にし、`nextRetryAt` を保存
- 次回run開始時に最大100件を再送

### Status

- run: `running` / `success` / `partial_failure` / `failed`
- event: `pending` / `sent` / `partially_sent` / `failed`
- delivery: `pending` / `sent` / `failed`

### Firestore Adapter

`create_firestore_client()` は Application Default Credentials を使用します。GitHub Actions では `google-github-actions/auth` がWIF credentialを提供します。

## Notification

### Console

```text
[タイトル] 本文
```

### Email

- `smtplib.SMTP`
- timeout 30秒
- `SMTP_USE_TLS=true` で STARTTLS
- `SMTP_USER` と `SMTP_PASS` が両方ある場合にlogin
- subject/bodyの `{title}` / `{message}` を置換
- `\n`, `\r`, `\t` のescape表記を実文字へ変換

### Retry

`DeliveryDispatcher` は Firestore backend で使用します。

- 合計試行回数: `max_retries + 1`
- デフォルト: 3回
- 待機: 60秒、120秒
- 最終例外を呼び出し元へ再送出

## 終了コード

- `0`: エラーなし
- `1`: 通知失敗、再送失敗を含む `partial_failure`、設定エラー
- 予期しないFirestore usecase例外: `runs` を `failed` で終了更新後に例外を再送出

## 設計上の境界

- source取得失敗と0件を区別しない
- AniListは最新25件のみ
- 同時runの排他制御なし
- Firestoreの `dedupeKey` は保存のみ
- `maxAttempts` は保存のみ
- dead-letterなし
- Firestoreの時刻は、TTL用`datetime`とその他のISO文字列が混在

詳細なFirestore構造は [`FIRESTORE_RUNTIME_DESIGN.md`](FIRESTORE_RUNTIME_DESIGN.md) を参照してください。
