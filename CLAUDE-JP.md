# CLAUDE-JP.md - アニメーター作画クレジット検知システム

## プロジェクト概要
指定されたアニメーターの作画クレジットがWebデータベース（Bangumi、AniList、作画@wiki）に新たに掲載されたことを自動検知し、通知するシステム。

## 技術スタック
- **言語:** Python 3.13（>= 3.11 必須）
- **プロジェクト管理:** Rye
- **CLI:** Click
- **ライブラリ:** python-dotenv, requests, beautifulsoup4
- **テスト:** pytest, responses（HTTPモック用）
- **リンター:** ruff（E/F/W/I/UP/B/SIM ルール）
- **型チェック:** mypy（disallow_untyped_defs）

## ディレクトリ構成
```
src/animator_credit_monitor/   # メインソースコード
├── main.py                    # Click CLI + オーケストレーション
├── scraper.py                 # Bangumi + AniList + 作画@wiki スクレイパー
├── notifier.py                # 通知ABC + Console実装
└── history.py                 # 差分検知 + 状態保存
tests/                         # テストファイル（pytest）
├── fixtures/                  # スクレイパーテスト用HTMLフィクスチャ
data/                          # 実行時状態（git除外）
docs/                          # 運用ドキュメント
devlog/                        # 開発ダイアリー
```

## 主要コマンド
```bash
rye sync                                    # 依存関係インストール
rye run pytest tests/ -v                    # 全テスト実行
rye run ruff check src/ tests/              # lint チェック
rye run mypy src/                           # 型チェック
rye run animator-credit-monitor check       # クレジットチェック実行
rye run animator-credit-monitor --help      # CLIヘルプ表示
```

## CLI オプション
```bash
animator-credit-monitor check               # 全ソースチェック
animator-credit-monitor check --bangumi-only # Bangumiのみ
animator-credit-monitor check --anilist-only # AniListのみ
animator-credit-monitor check --dry-run      # 状態保存なしでチェック
```

## アーキテクチャ
- **Notifier:** 抽象基底クラス（`Notifier`）に `ConsoleNotifier` をデフォルト実装。新しいサブクラスを実装することでDiscord/メール等に差し替え可能。
- **Scraper:** 3つのスクレイパークラス:
  - `BangumiScraper` — bangumi.tvの人物作品ページをスクレイプ。`<small>` タグから日本語タイトルを取得し、ない場合は中国語にフォールバック。`title_cn` フィールドを保持。
  - `AniListScraper` — AniList GraphQL API使用（認証不要）。日本語タイトル、ローマ字、役割、日付を返却。
  - `SakugaWikiScraper` — w.atwiki.jp/sakuga を検索（現在Cloudflare 403でブロック中）。
- **フォールバック:** 作画@wiki失敗時（403）は自動的にAniList APIにフォールバック。
- **History:** `HistoryManager` が `data/` 内のJSONベースの状態保存と差分検知を担当。履歴ファイルはソースID付き（例: `bangumi_50763_history.json`）で、アニメーター切替時にデータが混在しない。
- **Main:** Click CLIがオーケストレーション: 設定読込 → スクレイプ → 差分検知 → 変更があれば通知。

## 環境変数（.env）
- `TARGET_BANGUMI_ID` - 監視対象のBangumi人物ID
- `TARGET_NAME` - AniList/作画@wiki検索用のアニメーター名

## データ形式

### Bangumi作品
```json
{"id": "509986", "title": "アポカリプスホテル", "title_cn": "末日后酒店", "role": "原画", "info": "..."}
```

### AniList作品
```json
{"id": "180516", "title": "ウマ娘 シンデレラグレイ", "title_romaji": "Uma Musume: Cinderella Gray", "role": "Key Animation (OP)", "date": "2025-04"}
```

## ドキュメント管理
- `docs/` 配下のファイルは全て英語版と日本語版（`-JP` サフィックス）の両方を管理する
- 英語版を修正した場合は、必ず対応する `-JP.md` ファイルも更新すること
- 現在のバイリンガルドキュメント:
  - `docs/AUTOMATION.md` ↔ `docs/AUTOMATION-JP.md`
  - `docs/MAINTENANCE.md` ↔ `docs/MAINTENANCE-JP.md`

## テスト方針
- TDDアプローチ: テストを先に書いてから実装
- テスト名は日本語: `test_{分かりやすい日本語のシナリオ名}`
- `responses` ライブラリでHTTPモック
- `tests/fixtures/` にHTML解析テスト用フィクスチャ配置
- 全29テストで全モジュールをカバー
