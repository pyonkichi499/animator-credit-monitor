# Animator Credit Monitor

指定したアニメーターの作画クレジットを定期取得し、前回の取得結果との差分を通知する Python CLI です。

## 現在の実装

### データソース

| Source | 接続先 | 監視内容 |
|---|---|---|
| Bangumi | `https://bangumi.tv/person/{ID}/works` | 人物ページの作品・役職一覧を HTML から取得 |
| AniList | `https://graphql.anilist.co` | スタッフ名で検索し、最新25件のメディアクレジットを GraphQL API から取得 |

作画@wiki のスクレイパーは削除済みです。現在の name ベース監視は AniList を直接使用します。

### 通知先

- `console`: 標準出力（デフォルト）
- `email`: SMTP
- `NOTIFIERS=console,email` による複数通知先への配信

LINE Notify はサービス終了に伴い実装から削除済みです。

### 状態バックエンド

- `local`（デフォルト）: `data/*_history.json` に前回取得結果を保存
- `firestore`: `snapshots` / `runs` / `events` / `deliveries` を使用する Outbox 構成

Firestore バックエンドでは、通知失敗を `deliveries` に残し、次回実行の開始時に再送します。

## 必要環境

- Python 3.11 以上（`.python-version` は Python 3.13.2）
- [uv](https://docs.astral.sh/uv/) 0.11.24

## セットアップ

```bash
git clone https://github.com/pyonkichi499/animator-credit-monitor.git
cd animator-credit-monitor
uv sync --locked
cp .env.example .env
```

最小構成:

```env
# 少なくとも一方を設定
TARGET_BANGUMI_ID=12345
TARGET_NAME=アニメーター名

STATE_BACKEND=local
NOTIFIER=console
```

メール通知を使う場合:

```env
NOTIFIER=email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=from@example.com
SMTP_TO=to@example.com
SMTP_USER=
SMTP_PASS=
SMTP_USE_TLS=true
EMAIL_SUBJECT_TEMPLATE=[ACM] {title}
EMAIL_BODY_TEMPLATE={title}\n\n{message}
```

`SMTP_USER` と `SMTP_PASS` は両方が設定されている場合だけ SMTP 認証に使用されます。

## 使用方法

```bash
# 設定された全ソースを確認
uv run animator-credit-monitor check

# 状態更新なしで確認
uv run animator-credit-monitor check --dry-run

# Bangumi のみ
uv run animator-credit-monitor check --bangumi-only

# AniList のみ
uv run animator-credit-monitor check --anilist-only

# ヘルプ
uv run animator-credit-monitor --help
uv run animator-credit-monitor check --help
```

`--bangumi-only` と `--anilist-only` は同時指定できません。

### `--dry-run` の挙動

- 通知は実行されます。
- local: 履歴 JSON を更新しません。
- Firestore: 新規差分については `snapshots` / `events` / `deliveries` を更新せず、通知を直接送信します。
- Firestore の実行監査用 `runs` レコードは作成されます。
- Firestore の run 開始時に行う既存 delivery の再送は実行され、既存の delivery / event 状態を更新する場合があります。

## 環境変数

| 変数 | デフォルト | 説明 |
|---|---:|---|
| `TARGET_BANGUMI_ID` | 空 | Bangumi の人物ID |
| `TARGET_NAME` | 空 | AniList のスタッフ検索名 |
| `STATE_BACKEND` | `local` | `local` または `firestore` |
| `DATA_DIR` | `data` | local 履歴の保存先 |
| `NOTIFIER` | `console` | `console` または `email` |
| `NOTIFIERS` | 空 | カンマ区切りの通知先。設定時は `NOTIFIER` より優先 |
| `NOTIFY_RETRY_MAX_RETRIES` | `2` | 初回送信後の同一実行内リトライ回数 |
| `NOTIFY_RETRY_INITIAL_DELAY_SECONDS` | `60` | 初回リトライまでの秒数 |
| `GCP_PROJECT_ID` | 空 | Firestore 使用時は必須 |
| `FIRESTORE_DATABASE` | `(default)` | Firestore database ID |
| `FIRESTORE_COLLECTION_PREFIX` | 空 | コレクション名の接頭辞 |
| `SMTP_HOST` | 空 | email 使用時は必須 |
| `SMTP_PORT` | `587` | SMTP ポート。空文字は無効 |
| `SMTP_FROM` | 空 | email 使用時は必須 |
| `SMTP_TO` | 空 | email 使用時は必須 |
| `SMTP_USER` | 空 | SMTP 認証ユーザー |
| `SMTP_PASS` | 空 | SMTP 認証パスワード |
| `SMTP_USE_TLS` | `true` | STARTTLS の有効化 |
| `EMAIL_SUBJECT_TEMPLATE` | `{title}` | 件名テンプレート |
| `EMAIL_BODY_TEMPLATE` | `{message}` | 本文テンプレート |

少なくとも `TARGET_BANGUMI_ID` または `TARGET_NAME` の一方が必要です。`NOTIFIERS` に同じ通知先を重複指定することはできません。

email のテンプレート例は `templates/email_subject.template.txt` と `templates/email_body.template.txt` にあります。

## 差分検知と通知

- 初回実行は、取得できた全クレジットを新規として扱います。
- 空の取得結果は保存せず、既存の比較基準を維持します。
- 通知タイトルは `新しいクレジット (Bangumi)` または `新しいクレジット (AniList)` です。
- 本文は `検知件数: N` と連番付きクレジットで構成されます。
- AniList の代表的な作画役職は日本語へ変換され、未知の役職は原文のまま保持されます。

local バックエンドでは通知に失敗した場合、履歴を更新せず非0で終了します。Firestore バックエンドでは Outbox に保存後に snapshot を進め、失敗した delivery を次回実行へ持ち越します。

## GitHub Actions

- `.github/workflows/ci.yml`: `main` / `develop` への push と pull request で Ruff、mypy、pytest を実行
- `.github/workflows/daily-credit-check.yml`: 毎日 09:00 JST と手動実行で監視を実行

定期実行は `STATE_BACKEND=firestore` をデフォルトにしています。現在の workflow では次を **GitHub Variables** として設定してください。

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `TARGET_BANGUMI_ID` または `TARGET_NAME`
- `NOTIFIER=console` または `NOTIFIER=email`
- `SMTP_PORT=587`

email 使用時の追加設定:

**Variables**

- `SMTP_HOST`
- `SMTP_USE_TLS`
- 任意: `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE`

**Secrets**

- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_USER`
- `SMTP_PASS`

`TARGET_NAME` は Variable または Secret のどちらでも設定できます。GCP/WIF の3項目は workflow が `vars.*` を参照するため Variables に登録します。

定期実行ジョブは開始時に必須設定を検証します。`STATE_BACKEND=firestore` の場合は WIF 認証（`GCP_WORKLOAD_IDENTITY_PROVIDER` / `GCP_SERVICE_ACCOUNT` / `GCP_PROJECT_ID`）を必須とし、設定不足時は監視処理へ進む前に明示的に失敗します。schedule と手動実行の重複を避けるため `concurrency` で直列化し、ジョブには `timeout-minutes: 30` を設定しています。

詳細:

- [アーキテクチャ](docs/ARCHITECTURE-JP.md)
- [自動実行ガイド](docs/AUTOMATION-JP.md)
- [セットアップチェックリスト](docs/SETUP_CHECKLIST_JP.md)
- [GCP WIF セットアップ](docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md)
- [Firestore Runtime Design](docs/FIRESTORE_RUNTIME_DESIGN.md)

## 開発

```bash
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
uv build
```

uv 移行差分用のコミット補助スクリプトについては [`scripts/README.md`](scripts/README.md) を参照してください。通常実行はプレビューのみで、`--apply` を付けた場合だけコミットします。

## 既知の制約

- AniList は `perPage: 25` 固定で、ページネーションは未実装です。
- Bangumi は HTML セレクタに依存するため、サイト構造変更時に修正が必要です。
- Firestore の `dedupeKey` は保存されますが、現状は一意性制約として使用していません。
- `deliveries.maxAttempts` は保存されますが、現状の再送処理では上限判定に使用していません。
- GitHub Actions の重複実行は `concurrency` で直列化していますが、Firestore 側の transaction / dedupe / delivery lease による排他制御は未実装です。

## License

MIT
