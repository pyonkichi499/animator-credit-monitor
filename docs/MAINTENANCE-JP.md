# メンテナンスガイド

## スクレイピングセレクタ

### Bangumi (`scraper.py` - `BangumiScraper`)

スクレイパーは以下のCSSセレクタに依存している。BangumiのHTML構造が変更された場合、`src/animator_credit_monitor/scraper.py` の該当箇所を更新すること:

| セレクタ | 用途 | メソッド |
|---|---|---|
| `ul.browserFull` | 作品リストコンテナ | `_parse_works()` |
| `li.item` | 個々の作品エントリ | `_parse_works()` |
| `li[id]` | `id="item_{ID}"` 属性から作品ID取得 | `_parse_item()` |
| `li > div.inner > h3 > a.l` | 中国語タイトル + リンク | `_parse_item()` |
| `li > div.inner > h3 > small` | 日本語タイトル（存在しない場合あり） | `_parse_item()` |
| `li > div.inner > p.info` | 日付/スタジオ情報 | `_parse_item()` |
| `li > div.inner > span.badge_job` | 役割（例: 原画, 作画監督） | `_parse_item()` |
| `div.page_inner > span.p_edge` | ページネーション情報 `( X / Y )` | `_get_next_page_url()` |

**タイトル解決:** `<h3>` 内の `<small class="grey">` から日本語タイトルを優先取得。`<small>` タグが存在しない場合は `<a class="l">` の中国語タイトルをフォールバックとして使用。両方保持: `title`（日本語/フォールバック）と `title_cn`（常に中国語）。

### 作画@wiki (`scraper.py` - `SakugaWikiScraper`)

| セレクタ | 用途 | メソッド |
|---|---|---|
| `ul.search-list` | 検索結果コンテナ | `_parse_search_results()` |
| `li > a` | 結果リンク + タイトル | `_parse_search_results()` |

**注意:** 作画@wiki は現在 Cloudflare にブロックされている（HTTP 403）。User-Agentヘッダーに関係なく全リクエストが403を返す。この場合、システムは自動的に AniList API にフォールバックする。

### AniList (`scraper.py` - `AniListScraper`)

AniList は GraphQL API（`https://graphql.anilist.co`）を使用しており、HTMLスクレイピングではない。保守すべきCSSセレクタはなし。

| APIフィールド | マッピング先 | 備考 |
|---|---|---|
| `Staff.staffMedia.edges[].node.title.native` | `title` | 日本語タイトル（優先） |
| `Staff.staffMedia.edges[].node.title.romaji` | `title_romaji` | ローマ字タイトル |
| `Staff.staffMedia.edges[].staffRole` | `role` | 例: "Key Animation (ep 1)" |
| `Staff.staffMedia.edges[].node.id` | `id` | AniList メディアID |
| `Staff.staffMedia.edges[].node.startDate` | `date` | 形式: "YYYY-MM" |

**スクレイピングに対する優位性:** 認証不要、安定したAPI、セレクタ破損のリスクなし。1クエリあたり25件の制限あり（ページネーション未実装）。

## リクエスト間隔（Wait処理）

`BangumiScraper` には設定可能な `request_interval` パラメータ（デフォルト: 2.0秒）があり、ページ間にディレイを挿入する:

```python
scraper = BangumiScraper(request_interval=2.0)  # ページ間2秒
```

**目的:** 対象サーバーへの過剰な連続リクエストを防止。

**重要:**
- 1.0秒未満に設定しないこと
- ディレイはページ間のみ適用（最初のリクエストには適用されない）
- 対象サイトがエラーを返し始めた場合は間隔を延長すること
- AniList API は独自のレート制限（90リクエスト/分）がある — 本ツールでは問題にならない

## 状態リセット

### 全リセット

全履歴ファイルを削除すると「初回実行」状態に戻る:

```bash
rm data/*.json
```

次回実行時、全クレジットが新規として扱われ、全件の通知が送信される。

### ソース別リセット

履歴ファイルはソース + ID/名前で命名されている:

```bash
rm data/bangumi_50763_history.json     # Bangumi（人物ID 50763）のリセット
rm data/anilist_椛沢祥平_history.json   # AniList（特定アニメーター）のリセット
rm data/sakugawiki_椛沢祥平_history.json # 作画@wiki（特定アニメーター）のリセット
```

### 通知テスト

通知の動作確認手順:

1. テストしたいソースの履歴ファイルを削除
2. check コマンドを実行
3. 現在の全クレジットが新規として通知される

```bash
rm data/bangumi_*_history.json
rye run animator-credit-monitor check --bangumi-only
```

## エンコーディング

Bangumi は HTTPレスポンスヘッダーに `charset` を設定していないため、`requests` がデフォルトの `ISO-8859-1` を使用してしまう。スクレイパーでは `resp.encoding = resp.apparent_encoding` でオーバーライドし、UTF-8コンテンツ（日本語/中国語テキスト）を正しく処理している。

文字化けが発生した場合、`scraper.py` にこのエンコーディングオーバーライドが存在するか確認すること。

## 新しい通知バックエンドの追加

1. `src/animator_credit_monitor/notifier.py` で `Notifier` を継承した新しいクラスを作成:

```python
class DiscordNotifier(Notifier):
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def notify(self, title: str, message: str) -> None:
        # Discord webhook 通知を実装
        ...
```

2. `main.py` を更新し、設定に基づいて新しい notifier を使用（例: `.env` の `DISCORD_WEBHOOK_URL`）。

## コード品質コマンド

```bash
rye run pytest tests/ -v          # 全テスト実行
rye run ruff check src/ tests/    # lint チェック
rye run ruff check --fix src/ tests/  # lint 自動修正
rye run mypy src/                 # 型チェック
```
