# CLAUDE.md - Animator Credit Monitor

## Project Overview
Automated system to detect new animation credits for specified animators on web databases (Bangumi, Sakuga@wiki) and notify users of changes.

## Tech Stack
- **Language:** Python 3.11+
- **Project Management:** Rye
- **CLI:** Click
- **Libraries:** python-dotenv, requests, beautifulsoup4
- **Testing:** pytest, responses (HTTP mocking)

## Directory Structure
```
src/animator_credit_monitor/   # Main source code
├── main.py                    # Click CLI + orchestration
├── scraper.py                 # Bangumi + Sakuga@wiki scrapers
├── notifier.py                # Notification ABC + Console impl
└── history.py                 # Diff detection + state persistence
tests/                         # Test files (pytest)
├── fixtures/                  # HTML fixtures for scraper tests
data/                          # Runtime state (git-ignored)
docs/                          # Operational documentation
```

## Key Commands
```bash
rye sync                                    # Install dependencies
rye run pytest tests/ -v                    # Run all tests
rye run animator-credit-monitor check       # Run credit check
rye run animator-credit-monitor --help      # Show CLI help
```

## Architecture
- **Notifier:** Abstract base class (`Notifier`) with `ConsoleNotifier` default implementation. Swap to Discord/email by implementing new subclass.
- **Scraper:** `BangumiScraper` and `SakugaWikiScraper` classes. Each returns `list[dict]` of credits.
- **History:** `HistoryManager` handles JSON-based state persistence in `data/` and diff detection.
- **Main:** Click CLI orchestrates: load config → scrape → detect diff → notify if changes found.

## Environment Variables (.env)
- `TARGET_BANGUMI_ID` - Bangumi person ID to monitor
- `TARGET_NAME` - Animator name for Sakuga@wiki search

## Testing
- TDD approach: write tests first, then implement
- Test names in Japanese: `test_{descriptive_scenario_in_Japanese}`
- HTTP mocking with `responses` library
- Fixtures in `tests/fixtures/` for HTML parsing tests
