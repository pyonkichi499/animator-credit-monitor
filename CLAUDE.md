# CLAUDE.md - Animator Credit Monitor

## Project Overview
Automated system to detect new animation credits for specified animators on web databases (Bangumi, AniList, Sakuga@wiki) and notify users of changes.

## Tech Stack
- **Language:** Python 3.13 (requires >= 3.11)
- **Project Management:** Rye
- **CLI:** Click
- **Libraries:** python-dotenv, requests, beautifulsoup4, google-cloud-firestore
- **Testing:** pytest, responses (HTTP mocking)
- **Linting:** ruff (E/F/W/I/UP/B/SIM rules)
- **Type Checking:** mypy (disallow_untyped_defs)

## Directory Structure
```
src/animator_credit_monitor/   # Main source code
├── main.py                    # Click CLI + orchestration (routes local/firestore)
├── config.py                  # AppConfig dataclass + env parsing + validation
├── models.py                  # SourcePlan, SourceRunResult, RunReport value objects
├── ports.py                   # HistoryRepository / NotificationGateway protocols
├── usecase.py                 # MonitorUseCase (local backend)
├── firestore_usecase.py       # FirestoreOutboxMonitorUseCase (Firestore backend)
├── delivery.py                # DeliveryDispatcher + RetryPolicy + DeliveryTarget
├── firestore_store.py         # Firestore repositories (snapshots/runs/outbox)
├── formatters.py              # Diff → notification message formatters
├── scraper.py                 # Bangumi + AniList + Sakuga@wiki scrapers
├── notifier.py                # Notification ABC + Console/Email/Line impls
└── history.py                 # Local JSON diff detection + state persistence
tests/                         # Test files (pytest)
├── fixtures/                  # HTML fixtures for scraper tests
data/                          # Runtime state (git-ignored)
docs/                          # Operational & design documentation
templates/                     # Configuration templates
devlog/                        # Development diary
```

## Key Commands
```bash
rye sync                                    # Install dependencies
rye run pytest tests/ -v                    # Run all tests
rye run ruff check src/ tests/              # Lint check
rye run mypy src/                           # Type check
rye run animator-credit-monitor check       # Run credit check
rye run animator-credit-monitor --help      # Show CLI help
```

## CLI Options
```bash
animator-credit-monitor check               # Check all sources
animator-credit-monitor check --bangumi-only # Bangumi only
animator-credit-monitor check --anilist-only # Name-based source only (AniList direct)
animator-credit-monitor check --dry-run      # Check without saving state
```

## Architecture

### Clean Architecture Layers
- **Ports (protocols):** `HistoryRepository`, `NotificationGateway` — dependency injection interfaces.
- **Models:** `SourcePlan`, `SourceRunResult`, `RunReport` — frozen dataclasses for immutable value objects.
- **Use Cases:** `MonitorUseCase` (local) and `FirestoreOutboxMonitorUseCase` (Firestore) — pure business logic.
- **Config:** `AppConfig` dataclass with `load_app_config_from_env()` — validates all env vars upfront.
- **Delivery:** `DeliveryDispatcher` with `RetryPolicy` — exponential backoff retry for multi-target fanout.

### Dual Backend
- **`STATE_BACKEND=local`** (default): Uses `HistoryManager` (JSON files in `data/`).
- **`STATE_BACKEND=firestore`**: Uses Firestore collections (`snapshots`, `runs`, `events`, `deliveries`) with Outbox pattern for at-least-once delivery.

### Existing Components
- **Notifier:** Abstract base class (`Notifier`) with `ConsoleNotifier`, `EmailNotifier`, `LineNotifier`, `MultiNotifier`.
- **Scraper:** `BangumiScraper`, `AniListScraper`, `SakugaWikiScraper` (403 blocked).
- **History:** `HistoryManager` — JSON-based state in `data/`, source ID in filename.
- **Main:** Click CLI routes to local or Firestore backend based on config.

## Environment Variables (.env)
- `TARGET_BANGUMI_ID` - Bangumi person ID to monitor
- `TARGET_NAME` - Animator name for name-based monitoring (currently effectively AniList)
- `STATE_BACKEND` - `local` (default) or `firestore`
- `GCP_PROJECT_ID` - Required when `STATE_BACKEND=firestore`
- `FIRESTORE_DATABASE` - Firestore database (default: `(default)`)
- `FIRESTORE_COLLECTION_PREFIX` - Optional prefix for Firestore collections
- `NOTIFIER` / `NOTIFIERS` - Notification channel(s): `console`, `email`, `line`
- `NOTIFY_RETRY_MAX_RETRIES` - Retry count for delivery (default: 2)
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS` - Initial retry delay (default: 60)

## Data Format

### Bangumi works
```json
{"id": "509986", "title": "アポカリプスホテル", "title_cn": "末日后酒店", "role": "原画", "info": "..."}
```

### AniList works
```json
{"id": "180516", "title": "ウマ娘 シンデレラグレイ", "title_romaji": "Uma Musume: Cinderella Gray", "role": "原画 (OP)", "date": "2025-04"}
```

## Documentation
- All files in `docs/` are maintained in both English and Japanese (with `-JP` suffix)
- When modifying any English doc in `docs/`, always update the corresponding `-JP.md` file as well
- Current bilingual docs:
  - `docs/AUTOMATION.md` ↔ `docs/AUTOMATION-JP.md`
  - `docs/MAINTENANCE.md` ↔ `docs/MAINTENANCE-JP.md`
- Design docs (Firestore integration):
  - `docs/FIRESTORE_RUNTIME_DESIGN.md` — Execution flow, collections, retry policy
  - `docs/FIRESTORE_DESIGN_CHECKLIST.md` — Design decisions
  - `docs/FIRESTORE_SNAPSHOTS_AND_UPDATE_POLICY.md` — Snapshot update rules
  - `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md` — WIF authentication setup
  - `docs/SETUP_CHECKLIST_JP.md` — Step-by-step setup guide

## Testing
- TDD approach: write tests first, then implement
- Test names in Japanese: `test_{descriptive_scenario_in_Japanese}`
- HTTP mocking with `responses` library
- Fixtures in `tests/fixtures/` for HTML parsing tests
- Tests cover CLI, scraper, history, notifier, config, delivery, usecase, and formatters modules
