# Maintenance Guide

## Scraping Selectors

### Bangumi (`scraper.py` - `BangumiScraper`)

The scraper depends on the following CSS selectors. If Bangumi changes their HTML structure, update these in `src/animator_credit_monitor/scraper.py`:

| Selector | Purpose | Method |
|---|---|---|
| `ul.browserFull` | Works list container | `_parse_works()` |
| `li.item` | Individual work entry | `_parse_works()` |
| `li[id]` | Work ID from `id="item_{ID}"` attribute | `_parse_item()` |
| `li > div.inner > h3 > a.l` | Chinese title + link | `_parse_item()` |
| `li > div.inner > h3 > small` | Japanese title (may not exist) | `_parse_item()` |
| `li > div.inner > p.info` | Date/studio info | `_parse_item()` |
| `li > div.inner > span.badge_job` | Role (e.g., 原画, 作画監督) | `_parse_item()` |
| `div.page_inner > span.p_edge` | Pagination info `( X / Y )` | `_get_next_page_url()` |

**Title resolution:** Japanese title is preferred from `<small class="grey">` inside `<h3>`. If the `<small>` tag is absent, the Chinese title from `<a class="l">` is used as fallback. Both are stored: `title` (Japanese/fallback) and `title_cn` (always Chinese).

### Sakuga@wiki (`scraper.py` - `SakugaWikiScraper`)

| Selector | Purpose | Method |
|---|---|---|
| `ul.search-list` | Search results container | `_parse_search_results()` |
| `li > a` | Result link + title | `_parse_search_results()` |

**Note:** Sakuga@wiki is currently blocked by Cloudflare (HTTP 403). All requests return 403 regardless of User-Agent headers. When this happens, the system automatically falls back to AniList API.

### AniList (`scraper.py` - `AniListScraper`)

AniList uses a GraphQL API (`https://graphql.anilist.co`), not HTML scraping. No CSS selectors to maintain.

| API Field | Mapped to | Notes |
|---|---|---|
| `Staff.staffMedia.edges[].node.title.native` | `title` | Japanese title (preferred) |
| `Staff.staffMedia.edges[].node.title.romaji` | `title_romaji` | Romanized title |
| `Staff.staffMedia.edges[].staffRole` | `role` | e.g., "Key Animation (ep 1)" |
| `Staff.staffMedia.edges[].node.id` | `id` | AniList media ID |
| `Staff.staffMedia.edges[].node.startDate` | `date` | Format: "YYYY-MM" |

**Advantages over scraping:** No auth required, stable API, no risk of selector breakage. Limited to 25 results per query (pagination not yet implemented).

## Request Interval (Wait Processing)

The `BangumiScraper` has a configurable `request_interval` parameter (default: 2.0 seconds) that adds a delay between paginated requests:

```python
scraper = BangumiScraper(request_interval=2.0)  # 2 seconds between pages
```

**Purpose:** Prevent overloading the target server with rapid requests.

**Important:**
- Do not set this below 1.0 second
- The interval only applies between pages (not on the first request)
- If the target site starts returning errors, consider increasing the interval
- AniList API has its own rate limiting (90 requests/minute) — not an issue for this tool

## State Reset

### Full Reset

Delete all history files to force a "first run" state:

```bash
rm data/*.json
```

The next execution will treat all credits as new and send notifications for everything.

### Per-Source Reset

History files are named with source + ID/name:

```bash
rm data/bangumi_50763_history.json     # Reset Bangumi for person 50763
rm data/anilist_椛沢祥平_history.json   # Reset AniList for specific animator
rm data/sakugawiki_椛沢祥平_history.json # Reset Sakuga@wiki for specific animator
```

### Notification Test

To test that notifications work:

1. Delete the history file for the source you want to test
2. Run the check command
3. All current credits will be reported as new

```bash
rm data/bangumi_*_history.json
rye run animator-credit-monitor check --bangumi-only
```

## Encoding

Bangumi does not set `charset` in its HTTP response headers, causing `requests` to default to `ISO-8859-1`. The scraper overrides this with `resp.encoding = resp.apparent_encoding` to correctly handle UTF-8 content (Japanese/Chinese text).

If garbled text appears, check that this encoding override is still present in `scraper.py`.

## Adding a New Notification Backend

1. Create a new class that inherits from `Notifier` in `src/animator_credit_monitor/notifier.py`:

```python
class DiscordNotifier(Notifier):
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def notify(self, title: str, message: str) -> None:
        # Implement Discord webhook notification
        ...
```

2. Update `main.py` to use the new notifier based on configuration (e.g., `DISCORD_WEBHOOK_URL` in `.env`).

## Code Quality Commands

```bash
rye run pytest tests/ -v          # Run all tests
rye run ruff check src/ tests/    # Lint check
rye run ruff check --fix src/ tests/  # Auto-fix lint issues
rye run mypy src/                 # Type check
```
