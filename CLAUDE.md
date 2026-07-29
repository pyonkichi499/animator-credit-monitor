# CLAUDE.md - Animator Credit Monitor

## Project Overview

Python CLI that fetches animator credits from Bangumi and AniList, compares them with the previous state, and sends new-credit notifications to the console or email.

The current sources are **Bangumi / AniList** and the current notification backends are **console / email**. The Sakuga@wiki scraper and LINE Notify integration have been removed.

## Tech Stack

- Python 3.11+ (`.python-version`: 3.13.2)
- uv 0.11.24 / `uv.lock`
- Click / requests / BeautifulSoup / google-cloud-firestore
- pytest / responses / Ruff / mypy

## Directory Structure

```text
src/animator_credit_monitor/
├── main.py                # Click CLI, dependency wiring, backend/source selection
├── config.py              # Environment parsing and aggregated validation
├── models.py              # SourcePlan / SourceRunResult / RunReport
├── ports.py               # HistoryRepository / NotificationGateway
├── usecase.py             # Local-backend use case
├── firestore_usecase.py   # Firestore + Outbox use case
├── history.py             # JSON history persistence
├── firestore_store.py     # snapshots / runs / events / deliveries
├── delivery.py            # Notification targets and exponential backoff
├── scraper.py             # BangumiScraper / AniListScraper
├── notifier.py            # ConsoleNotifier / EmailNotifier / MultiNotifier
└── formatters.py          # Source-specific notification bodies
tests/                     # Unit tests and fake-git commit-script tests
docs/                      # Operations, Firestore, and GCP documentation
templates/                 # Email and SMTP configuration examples
scripts/commit.sh          # Review-first helper for the uv migration commits
```

## Key Commands

```bash
uv sync --locked
uv run animator-credit-monitor check
uv run animator-credit-monitor check --dry-run
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/ -v
uv build
```

## Current Architecture

### Sources

- `BangumiScraper`: paginates HTML and extracts work ID, Japanese/Chinese title, role, and info text.
- `AniListScraper`: uses GraphQL `Staff(search:)`. `staffMedia` is limited to the latest 25 entries; pagination is not implemented.

### Local backend

- `HistoryManager` atomically replaces `data/{source_key}_history.json`.
- The first successful fetch treats every item as new.
- A notification failure prevents the history from advancing.
- `--dry-run` still sends notifications but does not update history.

### Firestore backend

- `snapshots`: comparison baseline
- `runs`: execution audit
- `events`: detected-credit events
- `deliveries`: per-channel delivery state
- Up to 100 retryable deliveries are processed at the beginning of a run.
- For a new diff, the snapshot advances after the event and deliveries are committed in a batch.
- Runs record `success`, `partial_failure`, or `failed`; partial failure produces a non-zero CLI exit.
- `--dry-run` still creates a `runs` record, but does not update snapshots, events, or deliveries.
- Existing redeliveries are still processed at run start during a dry run and may update existing delivery/event state.

### Notifications

- `ConsoleNotifier`
- `EmailNotifier` with STARTTLS, optional SMTP AUTH, and `{title}` / `{message}` templates
- `MultiNotifier` attempts every configured backend and aggregates failures
- `DeliveryDispatcher` makes `max_retries + 1` attempts with a 2x delay multiplier

## Important Configuration Rules

- At least one of `TARGET_BANGUMI_ID` or `TARGET_NAME` is required.
- `STATE_BACKEND`: `local` / `firestore`
- `NOTIFIER`: `console` / `email`
- `NOTIFIERS`, when set, takes precedence over `NOTIFIER`.
- `GCP_PROJECT_ID` is required for Firestore.
- `SMTP_HOST`, `SMTP_FROM`, and `SMTP_TO` are required for email.
- `SMTP_PORT` must be an integer; an empty string is invalid.

## GitHub Actions

- CI: Ruff → mypy → pytest on pushes to `main`/`develop` and on pull requests
- Daily: 09:00 JST or `workflow_dispatch`
- WIF values `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_SERVICE_ACCOUNT` are GitHub Variables.
- The daily workflow defaults to Firestore and cannot start successfully without the required Variables.

## Current Limitations

- AniList is limited to 25 entries.
- `dedupeKey` is stored but is not currently enforced as a uniqueness constraint.
- `lastSnapshotHash` is stored, while diff detection still compares serialized JSON items.
- `maxAttempts=50` is stored but is not currently enforced by redelivery processing.
- Concurrent runs are not locked.

## Documentation

Update English/Japanese pairs together.

- `AUTOMATION.md` ↔ `AUTOMATION-JP.md`
- `MAINTENANCE.md` ↔ `MAINTENANCE-JP.md`
- `SETUP_CHECKLIST.md` ↔ `SETUP_CHECKLIST_JP.md`
- `ARCHITECTURE.md` ↔ `ARCHITECTURE-JP.md`
- Firestore/WIF documents: Japanese file ↔ `*_EN.md`

## Testing

- Unit tests cover business logic, CLI, scrapers, notifiers, and Firestore repositories/use cases.
- HTTP calls are mocked with `responses`.
- The commit helper uses fake `git` and fake `uv`, so its tests never modify the real repository.
