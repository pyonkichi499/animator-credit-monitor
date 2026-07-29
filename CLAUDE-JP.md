# CLAUDE-JP.md - Animator Credit Monitor

## プロジェクト概要

Bangumi と AniList から指定アニメーターのクレジットを取得し、前回状態との差分を console または email へ通知する Python CLI。

現在の監視ソースは **Bangumi / AniList**、通知先は **console / email**。作画@wiki と LINE Notify の実装は削除済み。

## 技術スタック

- Python 3.11+（`.python-version`: 3.13.2）
- uv 0.11.24 / `uv.lock`
- Click / requests / BeautifulSoup / google-cloud-firestore
- pytest / responses / Ruff / mypy

## ディレクトリ構成

```text
src/animator_credit_monitor/
├── main.py                # Click CLI、依存構築、backend/source の選択
├── config.py              # 環境変数の解析と一括バリデーション
├── models.py              # SourcePlan / SourceRunResult / RunReport
├── ports.py               # HistoryRepository / NotificationGateway
├── usecase.py             # local backend のユースケース
├── firestore_usecase.py   # Firestore + Outbox のユースケース
├── history.py             # JSON 履歴保存
├── firestore_store.py     # snapshots / runs / events / deliveries
├── delivery.py            # 通知ターゲットと指数バックオフ
├── scraper.py             # BangumiScraper / AniListScraper
├── notifier.py            # ConsoleNotifier / EmailNotifier / MultiNotifier
└── formatters.py          # ソース別通知本文
tests/                     # 単体テストと fake-git の commit script テスト
docs/                      # 運用・Firestore・GCP ドキュメント
templates/                 # email / SMTP 設定例
scripts/commit.sh          # uv 移行差分の review-first commit helper
```

## 主要コマンド

```bash
uv sync --locked
uv run animator-credit-monitor check
uv run animator-credit-monitor check --dry-run
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
uv build
```

## 現行アーキテクチャ

### Source

- `BangumiScraper`: HTML をページネーションし、作品ID・日本語/中国語タイトル・役職・情報文字列を取得
- `AniListScraper`: GraphQL `Staff(search:)` を使用。`staffMedia` は最新25件でページネーション未実装

### local backend

- `HistoryManager` が `data/{source_key}_history.json` を原子的に更新
- 初回は全件を差分として扱う
- 通知失敗時は履歴を更新しない
- `--dry-run` は通知するが履歴を更新しない

### Firestore backend

- `snapshots`: 差分比較基準
- `runs`: 実行監査
- `events`: 検知イベント
- `deliveries`: 通知先ごとの配送状態
- 実行開始時に最大100件の retryable delivery を再送
- 新規差分は event + deliveries のバッチ保存後に snapshot を更新
- `success` / `partial_failure` / `failed` を記録し、partial failure は CLI 非0終了
- `--dry-run` でも `runs` は作成するが、snapshot / event / delivery は更新しない
- ただし run 開始時の既存delivery再送は dry-run でも実行され、既存delivery/eventを更新し得る

### Notification

- `ConsoleNotifier`
- `EmailNotifier`（STARTTLS、任意の SMTP AUTH、`{title}` / `{message}` テンプレート）
- `MultiNotifier` は全通知先を試行して失敗を集約
- `DeliveryDispatcher` は `max_retries + 1` 回試行し、遅延を2倍ずつ増加

## 設定上の重要事項

- `TARGET_BANGUMI_ID` または `TARGET_NAME` の一方が必須
- `STATE_BACKEND`: `local` / `firestore`
- `NOTIFIER`: `console` / `email`
- `NOTIFIERS` を設定した場合は `NOTIFIER` より優先
- Firestore 使用時は `GCP_PROJECT_ID` が必須
- email 使用時は `SMTP_HOST`, `SMTP_FROM`, `SMTP_TO` が必須
- `SMTP_PORT` は整数。空文字は無効

## GitHub Actions

- CI: push (`main`, `develop`) / pull request で Ruff → mypy → pytest
- Daily: 09:00 JST、または `workflow_dispatch`
- WIF の `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT` は GitHub Variables
- Daily workflow は Firestore をデフォルトにするため、Variables 未設定では起動できない

## 実装上の制約

- AniList は25件まで
- `dedupeKey` は保存のみで、一意性チェックには未使用
- `lastSnapshotHash` は保存するが、差分判定は JSON シリアライズ比較
- `maxAttempts=50` は保存するが、再送上限には未使用
- 同時実行の排他制御なし

## ドキュメント管理

英語・日本語のペアを同時更新する。

- `AUTOMATION.md` ↔ `AUTOMATION-JP.md`
- `MAINTENANCE.md` ↔ `MAINTENANCE-JP.md`
- `SETUP_CHECKLIST.md` ↔ `SETUP_CHECKLIST_JP.md`
- `ARCHITECTURE.md` ↔ `ARCHITECTURE-JP.md`
- Firestore / WIF 文書: `*_EN.md` ↔ 日本語版

## テスト方針

- ビジネスロジック、CLI、scraper、notifier、Firestore repository/usecase を単体テスト
- 外部HTTPは `responses` でモック
- commit helper は fake `git` / fake `uv` を使用し、実リポジトリを変更せず検証
