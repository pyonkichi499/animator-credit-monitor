# Architecture

## Overview

Animator Credit Monitor is a Click-based Python CLI that:

1. fetches credit lists from Bangumi / AniList
2. compares them with previous state in local JSON or Firestore
3. sends new credits to console / email
4. stores execution results and the baseline for the next run

## Modules

| Module | Responsibility |
|---|---|
| `main.py` | CLI, configuration, dependency wiring, source/backend selection, exit code |
| `config.py` | Environment parsing, normalization, aggregated validation |
| `scraper.py` | Bangumi HTML and AniList GraphQL adapters |
| `formatters.py` | Standard notification message generation |
| `notifier.py` | Console / SMTP email and local multi-notifier |
| `delivery.py` | Firestore delivery targets and in-run retry |
| `history.py` | Local JSON loading, diff detection, atomic replacement |
| `usecase.py` | Local-backend monitoring flow |
| `firestore_store.py` | Firestore repositories and collection naming |
| `firestore_usecase.py` | Outbox, snapshot updates, redelivery, run audit |
| `models.py` | Source plans and run-result value objects |
| `ports.py` | Protocols used by the local use case |

## CLI Construction

`animator_credit_monitor.main:cli` is the entry point.

1. Load `.env` through `python-dotenv`.
2. Validate all settings with `load_app_config_from_env()`.
3. Validate CLI options and monitoring targets.
4. Select local or Firestore through `STATE_BACKEND`.
5. Build `SourcePlan` objects from `TARGET_BANGUMI_ID` / `TARGET_NAME`.
6. Decide the exit code from `RunReport`.

Configuration validation returns as many errors as possible in one result.

## Source Adapters

### Bangumi

- Uses `requests.Session` with browser-like headers.
- Fetches `/person/{id}/works`.
- Waits two seconds between pages by default.
- Falls back to the Chinese title when no Japanese title exists.
- On HTTP/connection error, returns already fetched pages when available, otherwise an empty list.

### AniList

- `POST https://graphql.anilist.co`
- Name search through `Staff(search:)`
- `staffMedia(sort: START_DATE_DESC, perPage: 25)`
- Prefers native title and falls back to romaji.
- Translates common animation roles to Japanese.
- Returns an empty list on HTTP/connection error or no matching staff.

An empty list cannot distinguish fetch failure from a genuinely empty result. Both backends preserve the existing comparison baseline in this case.

## Local Backend

```text
fetch
  → skip when empty
  → HistoryManager.detect_diff
  → call Notifier.notify when a diff exists
  → HistoryManager.save after notification success and when not dry-run
  → RunReport
```

Properties:

- History unit: `source_key`
- File: `DATA_DIR/{source_key}_history.json`
- First run: every item is new
- No diff: save the latest fetched result unless this is a dry run
- Notification failure: do not advance history
- Multiple notifiers: `MultiNotifier` attempts all and aggregates failures

## Firestore Backend

```text
start run
  → process retryable deliveries
  → for each source: fetch/diff
      → no diff: update snapshot
      → dry-run: direct notification
      → diff: batch event+deliveries
                → update snapshot
                → dispatch deliveries
                → aggregate event status
  → finish run
  → RunReport
```

### Outbox

- Event and deliveries are created in one Firestore batch.
- The snapshot advances after the batch succeeds.
- A notification failure marks the delivery as `failed` and stores `nextRetryAt`.
- The next run retries up to 100 due deliveries.

### Statuses

- Run: `running` / `success` / `partial_failure` / `failed`
- Event: `pending` / `sent` / `partially_sent` / `failed`
- Delivery: `pending` / `sent` / `failed`

### Firestore Adapter

`create_firestore_client()` uses Application Default Credentials. In GitHub Actions, `google-github-actions/auth` supplies credentials through WIF.

## Notification

### Console

```text
[title] message
```

### Email

- `smtplib.SMTP`
- 30-second timeout
- STARTTLS when `SMTP_USE_TLS=true`
- Login only when both `SMTP_USER` and `SMTP_PASS` are set
- Replaces `{title}` / `{message}` in subject and body templates
- Decodes textual `\n`, `\r`, and `\t` escapes

### Retry

`DeliveryDispatcher` is used by the Firestore backend.

- Total attempts: `max_retries + 1`
- Default: 3 attempts
- Delays: 60 seconds and 120 seconds
- Re-raises the last exception

## Exit Codes

- `0`: no errors
- `1`: notification failure, redelivery failure / `partial_failure`, or configuration error
- Unexpected Firestore use-case exception: attempt to finalize the run as `failed`, then re-raise

## Design Boundaries

- A fetch failure is not distinguishable from zero results.
- AniList is limited to the latest 25 entries.
- No concurrent-run locking.
- Firestore `dedupeKey` is stored only.
- `maxAttempts` is stored only.
- No dead-letter mechanism.
- Firestore timestamps mix TTL `datetime` values and ISO strings for other fields.

See [`FIRESTORE_RUNTIME_DESIGN_EN.md`](FIRESTORE_RUNTIME_DESIGN_EN.md) for the detailed Firestore schema and flow.
