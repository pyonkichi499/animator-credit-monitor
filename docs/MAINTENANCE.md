# Maintenance Guide

## Scraping Selectors

### Bangumi (`scraper.py` - `BangumiScraper`)

The scraper depends on the following CSS selectors. If Bangumi changes their HTML structure, update these in `src/animator_credit_monitor/scraper.py`:

| Selector | Purpose | Method |
|---|---|---|
| `ul.browserFull` | Works list container | `_parse_works()` |
| `li.item` | Individual work entry | `_parse_works()` |
| `li > div.inner > h3 > a.l` | Work title + link | `_parse_item()` |
| `li > div.inner > p.info` | Date/studio info | `_parse_item()` |
| `li > div.inner > span.badge_job` | Role (e.g., 原画, 作画監督) | `_parse_item()` |
| `div.page_inner > span.p_edge` | Pagination info `( X / Y )` | `_get_next_page_url()` |

### Sakuga@wiki (`scraper.py` - `SakugaWikiScraper`)

| Selector | Purpose | Method |
|---|---|---|
| `ul.search-list` | Search results container | `_parse_search_results()` |
| `li > a` | Result link + title | `_parse_search_results()` |

**Note:** Sakuga@wiki may block automated access (HTTP 403). The scraper uses browser-like User-Agent headers but this is not guaranteed to work. If access is consistently blocked, manual verification may be needed.

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

## State Reset

### Full Reset

Delete all history files to force a "first run" state:

```bash
rm data/*.json
```

The next execution will treat all credits as new and send notifications for everything.

### Per-Source Reset

Reset only one data source:

```bash
rm data/bangumi_history.json      # Reset Bangumi only
rm data/sakugawiki_history.json   # Reset Sakuga@wiki only
```

### Notification Test

To test that notifications work:

1. Delete the history file for the source you want to test
2. Run the check command
3. All current credits will be reported as new

```bash
rm data/bangumi_history.json
rye run animator-credit-monitor check --bangumi-only
```

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

2. Update `main.py` to use the new notifier based on configuration.
