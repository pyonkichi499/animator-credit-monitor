# Animator Credit Monitor

特定アニメーターの作画クレジットが Web 上のデータベースに新たに掲載されたことを自動検知し、通知するツール。

## Data Sources

| Source | URL | Description |
|---|---|---|
| Bangumi | `bangumi.tv/person/{ID}` | 中国のアニメデータベース。作品リスト (Filmography) の差分を監視 |
| 作画@wiki | `w.atwiki.jp/sakuga/` | 日本の作画情報 wiki。キーワード検索結果を監視 |

## Setup

### Prerequisites

- Python 3.11+
- [Rye](https://rye.astral.sh/)

### Installation

```bash
git clone https://github.com/pyonkichi499/animator-credit-monitor.git
cd animator-credit-monitor
rye sync
```

### Configuration

Copy the example env file and edit it:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Bangumi person ID (find it from the URL: bangumi.tv/person/{THIS_NUMBER})
TARGET_BANGUMI_ID=12345

# Animator name for Sakuga@wiki search
TARGET_NAME=アニメーター名
```

## Usage

### Check for new credits

```bash
rye run animator-credit-monitor check
```

### Options

```bash
# Dry run (check without saving state)
rye run animator-credit-monitor check --dry-run

# Check only Bangumi
rye run animator-credit-monitor check --bangumi-only

# Check only Sakuga@wiki
rye run animator-credit-monitor check --wiki-only
```

### Show help

```bash
rye run animator-credit-monitor --help
rye run animator-credit-monitor check --help
```

## Testing

```bash
rye run pytest tests/ -v
```

## State Management

- Credit history is stored in `data/*.json` files
- Delete these files to reset state (next run will treat all credits as new)
- See [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for details

## Automation

See [docs/AUTOMATION.md](docs/AUTOMATION.md) for cron/scheduled task setup.

## License

MIT
