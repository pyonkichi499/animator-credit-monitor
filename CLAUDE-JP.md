# CLAUDE-JP.md - アニメーター作画クレジット検知システム

## プロジェクト概要
指定されたアニメーターの作画クレジットがWebデータベース（Bangumi、作画@wiki）に新たに掲載されたことを自動検知し、通知するシステム。

## 技術スタック
- **言語:** Python 3.11+
- **プロジェクト管理:** Rye
- **CLI:** Click
- **ライブラリ:** python-dotenv, requests, beautifulsoup4
- **テスト:** pytest, responses（HTTPモック用）

## ディレクトリ構成
```
src/animator_credit_monitor/   # メインソースコード
├── main.py                    # Click CLI + オーケストレーション
├── scraper.py                 # Bangumi + 作画@wiki スクレイパー
├── notifier.py                # 通知ABC + Console実装
└── history.py                 # 差分検知 + 状態保存
tests/                         # テストファイル（pytest）
├── fixtures/                  # スクレイパーテスト用HTMLフィクスチャ
data/                          # 実行時状態（git除外）
docs/                          # 運用ドキュメント
```

## 主要コマンド
```bash
rye sync                                    # 依存関係インストール
rye run pytest tests/ -v                    # 全テスト実行
rye run animator-credit-monitor check       # クレジットチェック実行
rye run animator-credit-monitor --help      # CLIヘルプ表示
```

## アーキテクチャ
- **Notifier:** 抽象基底クラス（`Notifier`）に `ConsoleNotifier` をデフォルト実装。新しいサブクラスを実装することでDiscord/メール等に差し替え可能。
- **Scraper:** `BangumiScraper` と `SakugaWikiScraper` クラス。各クレジットを `list[dict]` で返却。
- **History:** `HistoryManager` が `data/` 内のJSONベースの状態保存と差分検知を担当。
- **Main:** Click CLIがオーケストレーション: 設定読込 → スクレイプ → 差分検知 → 変更があれば通知。

## 環境変数（.env）
- `TARGET_BANGUMI_ID` - 監視対象のBangumi人物ID
- `TARGET_NAME` - 作画@wiki検索用のアニメーター名

## テスト方針
- TDDアプローチ: テストを先に書いてから実装
- テスト名は日本語: `test_{分かりやすい日本語のシナリオ名}`
- `responses` ライブラリでHTTPモック
- `tests/fixtures/` にHTML解析テスト用フィクスチャ配置
