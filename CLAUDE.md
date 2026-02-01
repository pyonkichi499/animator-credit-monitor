# CLAUDE.md - Animator Credit Monitor

## Project Overview
Automated system to detect new animation credits for specified animators on web databases (Bangumi, AniList, Sakuga@wiki) and notify users of changes.

## Tech Stack
- **Language:** Python 3.13 (requires >= 3.11)
- **Project Management:** Rye
- **CLI:** Click
- **Libraries:** python-dotenv, requests, beautifulsoup4
- **Testing:** pytest, responses (HTTP mocking)
- **Linting:** ruff (E/F/W/I/UP/B/SIM rules)
- **Type Checking:** mypy (disallow_untyped_defs)

## Directory Structure
```
src/animator_credit_monitor/   # Main source code
├── main.py                    # Click CLI + orchestration
├── scraper.py                 # Bangumi + AniList + Sakuga@wiki scrapers
├── notifier.py                # Notification ABC + Console impl
└── history.py                 # Diff detection + state persistence
tests/                         # Test files (pytest)
├── fixtures/                  # HTML fixtures for scraper tests
data/                          # Runtime state (git-ignored)
docs/                          # Operational documentation
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
animator-credit-monitor check --anilist-only # AniList only
animator-credit-monitor check --dry-run      # Check without saving state
```

## Architecture
- **Notifier:** Abstract base class (`Notifier`) with `ConsoleNotifier` default implementation. Swap to Discord/email by implementing new subclass.
- **Scraper:** Three scraper classes:
  - `BangumiScraper` — Scrapes bangumi.tv person works page. Returns Japanese titles from `<small>` tag, falling back to Chinese titles. Includes `title_cn` field.
  - `AniListScraper` — Uses AniList GraphQL API (no auth required). Returns Japanese titles, romaji, roles, and dates.
  - `SakugaWikiScraper` — Searches w.atwiki.jp/sakuga (currently blocked by Cloudflare 403).
- **Fallback:** When Sakuga@wiki fails (403), automatically falls back to AniList API.
- **History:** `HistoryManager` handles JSON-based state persistence in `data/` and diff detection. History files are named with source ID (e.g., `bangumi_50763_history.json`) to avoid mixing data when switching animators.
- **Main:** Click CLI orchestrates: load config → scrape → detect diff → notify if changes found.

## Environment Variables (.env)
- `TARGET_BANGUMI_ID` - Bangumi person ID to monitor
- `TARGET_NAME` - Animator name for AniList/Sakuga@wiki search

## Data Format

### Bangumi works
```json
{"id": "509986", "title": "アポカリプスホテル", "title_cn": "末日后酒店", "role": "原画", "info": "..."}
```

### AniList works
```json
{"id": "180516", "title": "ウマ娘 シンデレラグレイ", "title_romaji": "Uma Musume: Cinderella Gray", "role": "Key Animation (OP)", "date": "2025-04"}
```

## Documentation
- All files in `docs/` are maintained in both English and Japanese (with `-JP` suffix)
- When modifying any English doc in `docs/`, always update the corresponding `-JP.md` file as well
- Current bilingual docs:
  - `docs/AUTOMATION.md` ↔ `docs/AUTOMATION-JP.md`
  - `docs/MAINTENANCE.md` ↔ `docs/MAINTENANCE-JP.md`

## Testing
- TDD approach: write tests first, then implement
- Test names in Japanese: `test_{descriptive_scenario_in_Japanese}`
- HTTP mocking with `responses` library
- Fixtures in `tests/fixtures/` for HTML parsing tests
- 29 tests covering all modules
