# Animator Credit Monitor

特定アニメーターの作画クレジットが Web 上のデータベースに新たに掲載されたことを自動検知し、通知するツール。

## Data Sources

| Source | URL | Description |
|---|---|---|
| Bangumi | `bangumi.tv/person/{ID}` | 中国のアニメデータベース。作品リスト (Filmography) の差分を監視 |
| AniList | `graphql.anilist.co` | スタッフクレジットを API 経由で取得して差分監視 |
| 作画@wiki | `w.atwiki.jp/sakuga/` | 日本の作画情報 wiki。※現在は Cloudflare 403 により実運用では利用不可 |

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Installation

```bash
git clone https://github.com/pyonkichi499/animator-credit-monitor.git
cd animator-credit-monitor
uv sync --locked
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

# State backend: local | firestore
STATE_BACKEND=local

# Animator name for AniList search
TARGET_NAME=アニメーター名

# Notification backend: console | email | line
NOTIFIER=console

# Retry (in-run, exponential backoff)
NOTIFY_RETRY_MAX_RETRIES=2
NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60

# Firestore backend settings (required when STATE_BACKEND=firestore)
GCP_PROJECT_ID=your-gcp-project-id
FIRESTORE_DATABASE=(default)
FIRESTORE_COLLECTION_PREFIX=

# Email notifier settings (required when NOTIFIER=email)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=from@example.com
SMTP_TO=to@example.com
SMTP_USER=
SMTP_PASS=
SMTP_USE_TLS=true
# Optional templates (variables: {title}, {message})
EMAIL_SUBJECT_TEMPLATE=[ACM] {title}
EMAIL_BODY_TEMPLATE={title}\n\n{message}

# LINE notifier settings (required when NOTIFIER=line)
LINE_NOTIFY_TOKEN=your_token
# Optional
LINE_NOTIFY_API_URL=https://notify-api.line.me/api/notify
# Optional template (variables: {title}, {message})
LINE_MESSAGE_TEMPLATE={title}\n{message}
```

## Usage

### Check for new credits

```bash
uv run animator-credit-monitor check
```

### Options

```bash
# Dry run (check without saving state)
uv run animator-credit-monitor check --dry-run

# Check only Bangumi
uv run animator-credit-monitor check --bangumi-only

# Check only AniList/name-based source
uv run animator-credit-monitor check --anilist-only
```

> 現状メモ: name ベースの監視は AniList を直接利用します。
> 作画@wiki は現在 403 のため、運用対象から外しています。

### Show help

```bash
uv run animator-credit-monitor --help
uv run animator-credit-monitor check --help
```

## Notifications

- `NOTIFIER=console` (default): print to stdout
- `NOTIFIER=email`: send via SMTP (`SMTP_*` required)
- `NOTIFIER=line`: send via LINE Notify compatible API (`LINE_NOTIFY_TOKEN` required)
- `NOTIFIERS=email,line`: fan-out to both email and LINE in one run
- Message templates can use `{title}` and `{message}` placeholders
- Example templates are provided under `templates/`:
  - `templates/email_subject.template.txt`
  - `templates/email_body.template.txt`
  - `templates/line_message.template.txt`

### Notification message format

- Title: `新しいクレジット (Bangumi|AniList)`
- Body:
  - First line: `検知件数: N`
  - Following lines: numbered credit entries (`1. ...`, `2. ...`)
- Templates can use `{title}` and `{message}` to wrap/reformat the standardized payload.

## GitHub Actions (Scheduled Run)

A workflow is provided at `.github/workflows/daily-credit-check.yml`.

1. Open **Settings → Secrets and variables → Actions** in your GitHub repository.
2. Configure **GitHub OIDC / Workload Identity Federation** on GCP (recommended, no service account key JSON in GitHub).
   - Create a GCP service account for Firestore access
   - Create Workload Identity Pool + Provider for GitHub OIDC
   - Allow your GitHub repo/branch to impersonate the service account
   - Add these as **GitHub Variables** (non-secret):
     - `GCP_WORKLOAD_IDENTITY_PROVIDER`
     - `GCP_SERVICE_ACCOUNT`
     - `GCP_PROJECT_ID`
3. Add monitoring/notifier settings as **GitHub Variables** (non-secret):
   - `TARGET_BANGUMI_ID` (optional, for Bangumi monitoring)
   - `NOTIFIER` (`email` or `line`)
   - or `NOTIFIERS` (`email,line`) to send to both
   - `STATE_BACKEND` (`firestore` recommended for GitHub Actions)
   - `FIRESTORE_DATABASE` (`(default)` if omitted)
   - `FIRESTORE_COLLECTION_PREFIX` (optional)
   - `NOTIFY_RETRY_MAX_RETRIES` (default `2`)
   - `NOTIFY_RETRY_INITIAL_DELAY_SECONDS` (default `60`)
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS` (if using email)
4. Add credentials as **GitHub Secrets** (secret):
   - `TARGET_NAME` (if you prefer to keep it private)
   - Email: `SMTP_FROM`, `SMTP_TO`, `SMTP_USER`, `SMTP_PASS`
   - LINE: `LINE_NOTIFY_TOKEN` (optional: `LINE_NOTIFY_API_URL`)
5. Run from **Actions → Daily Credit Check → Run workflow** for first validation.

### Firestore Collections (when `STATE_BACKEND=firestore`)

- `snapshots`: diff comparison baseline (no TTL)
- `runs`: execution summaries (`30d` TTL recommended)
- `events`: detected credit events / outbox (`30d` TTL recommended)
- `deliveries`: notifier delivery states for retry/redelivery (`30d` TTL recommended)

### Secrets templates (GitHub Actions)

#### Email notifier (`NOTIFIER=email`)

```text
NOTIFIER=email
TARGET_NAME=監視対象名
TARGET_BANGUMI_ID=12345
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_FROM=from@example.com
SMTP_TO=to@example.com
SMTP_USER=your_user
SMTP_PASS=your_password
SMTP_USE_TLS=true
EMAIL_SUBJECT_TEMPLATE=[ACM] {title}
EMAIL_BODY_TEMPLATE={title}\n\n{message}
```

#### Email notifier (SendGrid preset)

```text
NOTIFIER=email
TARGET_NAME=監視対象名
TARGET_BANGUMI_ID=12345
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_FROM=verified-sender@example.com
SMTP_TO=destination@example.com
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_SUBJECT_TEMPLATE=[ACM] {title}
EMAIL_BODY_TEMPLATE={title}\n\n{message}
```

> `SMTP_USER=apikey` + `SMTP_PASS=<SendGrid API key>` がSendGridのSMTP認証セットです。
> 同じ内容は `templates/sendgrid_github_secrets.template.txt` にもあります。

#### Email notifier (Gmail SMTP preset)

```text
STATE_BACKEND=firestore
GCP_PROJECT_ID=your-gcp-project-id
TARGET_NAME=監視対象名
TARGET_BANGUMI_ID=12345

NOTIFIER=email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_FROM=your-gmail-address@gmail.com
SMTP_TO=destination@example.com
SMTP_USER=your-gmail-address@gmail.com
SMTP_PASS=your-16-char-app-password
EMAIL_SUBJECT_TEMPLATE=[ACM] {title}
EMAIL_BODY_TEMPLATE={title}\n\n{message}
```

> Gmail SMTP は通常のGoogleアカウントパスワードではなく、App Password を使ってください。
> WIF を使う GCP セットアップ手順は `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md` を参照。

#### LINE notifier (`NOTIFIER=line`)

```text
NOTIFIER=line
TARGET_NAME=監視対象名
TARGET_BANGUMI_ID=12345
LINE_NOTIFY_TOKEN=your_token
LINE_NOTIFY_API_URL=https://notify-api.line.me/api/notify
LINE_MESSAGE_TEMPLATE={title}\n{message}
```

#### Email + LINE notifier (both)

```text
NOTIFIERS=email,line
TARGET_NAME=監視対象名
TARGET_BANGUMI_ID=12345

# Email side
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_FROM=verified-sender@example.com
SMTP_TO=destination@example.com
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMTP_USE_TLS=true

# LINE side
LINE_NOTIFY_TOKEN=your_token
LINE_NOTIFY_API_URL=https://notify-api.line.me/api/notify
```

## Testing

```bash
uv run pytest tests/ -v
```

## State Management

- Credit history is stored in `data/*.json` files
- Delete these files to reset state (next run will treat all credits as new)
- See [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for details

## Automation

See [docs/AUTOMATION.md](docs/AUTOMATION.md) for cron/scheduled task setup.

## License

MIT
