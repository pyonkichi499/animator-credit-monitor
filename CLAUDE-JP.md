# CLAUDE-JP.md - アニメーター作画クレジット検知システム

## プロジェクト概要
指定されたアニメーターの作画クレジットがWebデータベース（Bangumi、AniList、作画@wiki）に新たに掲載されたことを自動検知し、通知するシステム。

## 技術スタック
- **言語:** Python 3.13（>= 3.11 必須）
- **プロジェクト管理:** uv
- **CLI:** Click
- **ライブラリ:** python-dotenv, requests, beautifulsoup4, google-cloud-firestore
- **テスト:** pytest, responses（HTTPモック用）
- **リンター:** ruff（E/F/W/I/UP/B/SIM ルール）
- **型チェック:** mypy（disallow_untyped_defs）

## ディレクトリ構成
```
src/animator_credit_monitor/   # メインソースコード
├── main.py                    # Click CLI + オーケストレーション (local/firestore 振り分け)
├── config.py                  # AppConfig dataclass + 環境変数解析 + バリデーション
├── models.py                  # SourcePlan, SourceRunResult, RunReport 値オブジェクト
├── ports.py                   # HistoryRepository / NotificationGateway プロトコル
├── usecase.py                 # MonitorUseCase (localバックエンド)
├── firestore_usecase.py       # FirestoreOutboxMonitorUseCase (Firestoreバックエンド)
├── delivery.py                # DeliveryDispatcher + RetryPolicy + DeliveryTarget
├── firestore_store.py         # Firestore リポジトリ (snapshots/runs/outbox)
├── formatters.py              # 差分 → 通知メッセージ フォーマッター
├── scraper.py                 # Bangumi + AniList + 作画@wiki スクレイパー
├── notifier.py                # 通知ABC + Console/Email/Line 実装
└── history.py                 # ローカルJSON差分検知 + 状態保存
tests/                         # テストファイル（pytest）
├── fixtures/                  # スクレイパーテスト用HTMLフィクスチャ
data/                          # 実行時状態（git除外）
docs/                          # 運用・設計ドキュメント
templates/                     # 設定テンプレート
devlog/                        # 開発ダイアリー
```

## 主要コマンド
```bash
uv sync --locked                            # 依存関係インストール
uv run pytest tests/ -v                     # 全テスト実行
uv run ruff check src/ tests/               # lint チェック
uv run mypy src/                            # 型チェック
uv run animator-credit-monitor check        # クレジットチェック実行
uv run animator-credit-monitor --help       # CLIヘルプ表示
```

## CLI オプション
```bash
animator-credit-monitor check               # 全ソースチェック
animator-credit-monitor check --bangumi-only # Bangumiのみ
animator-credit-monitor check --anilist-only # nameベースソースのみ（AniList直利用）
animator-credit-monitor check --dry-run      # 状態保存なしでチェック
```

## アーキテクチャ

### クリーンアーキテクチャ層
- **Ports (プロトコル):** `HistoryRepository`, `NotificationGateway` — 依存性注入インターフェース。
- **Models:** `SourcePlan`, `SourceRunResult`, `RunReport` — frozen dataclass による不変値オブジェクト。
- **Use Cases:** `MonitorUseCase` (local) と `FirestoreOutboxMonitorUseCase` (Firestore) — 純粋なビジネスロジック。
- **Config:** `AppConfig` dataclass と `load_app_config_from_env()` — 全環境変数を事前バリデーション。
- **Delivery:** `DeliveryDispatcher` と `RetryPolicy` — 指数バックオフリトライによるマルチターゲット配信。

### デュアルバックエンド
- **`STATE_BACKEND=local`** (デフォルト): `HistoryManager` を使用（`data/` 内のJSONファイル）。
- **`STATE_BACKEND=firestore`**: Firestore コレクション（`snapshots`, `runs`, `events`, `deliveries`）を使用。Outbox パターンによる at-least-once 配信保証。

### 既存コンポーネント
- **Notifier:** 抽象基底クラス（`Notifier`）に `ConsoleNotifier`, `EmailNotifier`, `LineNotifier`, `MultiNotifier` を実装。
- **Scraper:** `BangumiScraper`, `AniListScraper`, `SakugaWikiScraper`（403でブロック中）。
- **History:** `HistoryManager` — `data/` 内のJSONベース状態保存。ソースID付きファイル名。
- **Main:** Click CLI が設定に基づき local または Firestore バックエンドに振り分け。

## 環境変数（.env）
- `TARGET_BANGUMI_ID` - 監視対象のBangumi人物ID
- `TARGET_NAME` - nameベース監視用のアニメーター名（現状は実質AniList）
- `STATE_BACKEND` - `local`（デフォルト）または `firestore`
- `GCP_PROJECT_ID` - `STATE_BACKEND=firestore` 時に必須
- `FIRESTORE_DATABASE` - Firestore データベース（デフォルト: `(default)`）
- `FIRESTORE_COLLECTION_PREFIX` - Firestore コレクションのオプション接頭辞
- `NOTIFIER` / `NOTIFIERS` - 通知チャンネル: `console`, `email`, `line`
- `NOTIFY_RETRY_MAX_RETRIES` - 配信リトライ回数（デフォルト: 2）
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS` - 初回リトライ遅延（デフォルト: 60）

## データ形式

### Bangumi作品
```json
{"id": "509986", "title": "アポカリプスホテル", "title_cn": "末日后酒店", "role": "原画", "info": "..."}
```

### AniList作品
```json
{"id": "180516", "title": "ウマ娘 シンデレラグレイ", "title_romaji": "Uma Musume: Cinderella Gray", "role": "原画 (OP)", "date": "2025-04"}
```

## ドキュメント管理
- `docs/` 配下のファイルは全て英語版と日本語版（`-JP` サフィックス）の両方を管理する
- 英語版を修正した場合は、必ず対応する `-JP.md` ファイルも更新すること
- 現在のバイリンガルドキュメント:
  - `docs/AUTOMATION.md` ↔ `docs/AUTOMATION-JP.md`
  - `docs/MAINTENANCE.md` ↔ `docs/MAINTENANCE-JP.md`
- 設計ドキュメント（Firestore統合、バイリンガル JP ↔ EN）:
  - `docs/FIRESTORE_RUNTIME_DESIGN.md` ↔ `docs/FIRESTORE_RUNTIME_DESIGN_EN.md` — 実行フロー、コレクション、リトライポリシー
  - `docs/FIRESTORE_DESIGN_CHECKLIST.md` ↔ `docs/FIRESTORE_DESIGN_CHECKLIST_EN.md` — 設計判断
  - `docs/FIRESTORE_SNAPSHOTS_AND_UPDATE_POLICY.md` ↔ `docs/FIRESTORE_SNAPSHOTS_AND_UPDATE_POLICY_EN.md` — スナップショット更新ルール
  - `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md` ↔ `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS_EN.md` — WIF認証セットアップ
  - `docs/SETUP_CHECKLIST_JP.md` ↔ `docs/SETUP_CHECKLIST.md` — ステップバイステップ構築手順

## テスト方針
- TDDアプローチ: テストを先に書いてから実装
- テスト名は日本語: `test_{分かりやすい日本語のシナリオ名}`
- `responses` ライブラリでHTTPモック
- `tests/fixtures/` にHTML解析テスト用フィクスチャ配置
- CLI / scraper / history / notifier / config / delivery / usecase / formatters モジュールをテストでカバー
