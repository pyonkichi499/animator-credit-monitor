# Maintenance Guide

## Data Sources

### Bangumi (`BangumiScraper`)

`src/animator_credit_monitor/scraper.py` depends on the following HTML structure.

| Selector | Purpose |
|---|---|
| `ul.browserFull` | Work list |
| `li.item` | Work entry |
| `li[id]` | Extract the work ID from `item_{ID}` |
| `div.inner > h3 > a.l` | Chinese title |
| `div.inner > h3 > small` | Japanese title; falls back to the Chinese title |
| `div.inner > p.info` | Date/studio information |
| `div.inner > span.badge_job` | Staff role |
| `div.page_inner > span.p_edge` | `(current / total)` pagination text |

The default interval between pages is `request_interval=2.0` seconds. There is no delay before the first request.

The scraper uses `resp.apparent_encoding` because Bangumi may omit a response charset.

### AniList (`AniListScraper`)

The scraper uses AniList GraphQL `Staff(search:)` and `staffMedia(sort: START_DATE_DESC, perPage: 25)`.

| API field | Output |
|---|---|
| `node.id` | `id` |
| `node.title.native` | preferred `title` |
| `node.title.romaji` | `title_romaji`, and fallback `title` |
| `staffRole` | `role` |
| `node.startDate` | `date` (`YYYY-MM`) |

Common animation roles are translated to Japanese; unknown roles are preserved. Pagination is not implemented, so at most 25 entries are returned.

## Local State

History files:

```text
data/bangumi_{person_id}_history.json
data/anilist_{target_name}_history.json
```

Writes use a temporary file followed by `replace`.

### Reset

All sources:

```bash
rm data/*.json
```

Bangumi only:

```bash
rm data/bangumi_*_history.json
```

AniList only:

```bash
rm data/anilist_*_history.json
```

The next fetch treats every item from a reset source as new. With email enabled, this may send a full-list notification.

## Firestore State

Collections:

- `snapshots`: comparison baseline, no TTL
- `runs`: execution audit, recommended 30-day TTL on `expiresAt`
- `events`: detected events, recommended 30-day TTL
- `deliveries`: delivery and redelivery state, recommended 30-day TTL

With `FIRESTORE_COLLECTION_PREFIX=dev`, collection names become `dev_snapshots`, and so on.

Deleting a target snapshot makes every item new on the next run. Deleting events or deliveries may lose pending notifications; inspect them before removal.

## Notification Backends

- `ConsoleNotifier`: stdout
- `EmailNotifier`: SMTP, STARTTLS, optional authentication, and templates
- `MultiNotifier`: attempts every notifier and aggregates failures in `MultiNotifierError`

The currently valid configuration values are `console` and `email`.

### Adding a Notification Backend

1. Implement `Notifier`.
2. Add the type and required settings to `config.py`.
3. Wire it in `main.py::_build_delivery_targets()`.
4. Add notifier, config, CLI, and delivery tests.
5. Update `.env.example`, the workflow, README, and Automation/Setup documentation.

## Firestore Delivery and Redelivery

- In-run attempts: `max_retries + 1`
- Default: initial attempt plus two retries, waiting 60 then 120 seconds
- At run start, retry up to 100 `pending` / `failed` deliveries with `nextRetryAt <= now`
- Event status: `sent` / `partially_sent` / `failed`

`maxAttempts=50` is currently stored but is not enforced as a redelivery stop condition.

## Code Quality

```bash
uv lock --check
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
uv build
```

## Notification Message

- Title: `新しいクレジット (Bangumi|AniList)`
- First line: `検知件数: N`
- Following lines: `1. title [role] (info/date)`
- Email template variables: `{title}`, `{message}`

An unknown template variable raises `ValueError`.

## Known Implementation Limitations

- AniList is limited to 25 entries.
- Bangumi is sensitive to HTML selector changes.
- Firestore `dedupeKey` is not used for uniqueness enforcement.
- `lastSnapshotHash` is not used to accelerate diff calculation.
- `maxAttempts` is not enforced.
- Concurrent GitHub Actions / Firestore runs are not locked.
