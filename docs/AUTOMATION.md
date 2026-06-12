# Automation Guide

## cron (Linux/macOS)

### Setup

1. Open the crontab editor:

```bash
crontab -e
```

2. Add a daily check (e.g., every day at 9:00 AM):

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /path/to/.rye/shims/rye run animator-credit-monitor check >> /path/to/logs/monitor.log 2>&1
```

### Recommended Frequency

- **1 day / 1 time** is recommended to avoid excessive load on target sites
- Bangumi and Sakuga@wiki are community-maintained databases; please be respectful of their server resources

### Log Output

Add a log rotation:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /path/to/.rye/shims/rye run animator-credit-monitor check >> /path/to/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

## Task Scheduler (Windows)

1. Open Task Scheduler
2. Create a new Basic Task
3. Set trigger to "Daily"
4. Set action to "Start a program":
   - Program: `rye`
   - Arguments: `run animator-credit-monitor check`
   - Start in: `C:\path\to\animator-credit-monitor`

## systemd Timer (Linux)

### Service file (`/etc/systemd/user/animator-monitor.service`)

```ini
[Unit]
Description=Animator Credit Monitor

[Service]
Type=oneshot
WorkingDirectory=/path/to/animator-credit-monitor
ExecStart=/path/to/.rye/shims/rye run animator-credit-monitor check
```

### Timer file (`/etc/systemd/user/animator-monitor.timer`)

```ini
[Unit]
Description=Run Animator Credit Monitor daily

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### Enable

```bash
systemctl --user enable --now animator-monitor.timer
```

## GitHub Actions (Scheduled)

This repository includes `.github/workflows/daily-credit-check.yml`.

### Setup

1. Go to **Settings → Secrets and variables → Actions**.
2. Register **Variables** (non-secret, visible in logs):
   - `TARGET_BANGUMI_ID` (optional, for Bangumi monitoring)
   - `NOTIFIER` (`console`, `email`, or `line`)
   - `NOTIFIERS` (optional multi-destination, e.g. `email,line`)
   - `STATE_BACKEND` (`firestore` recommended for GitHub Actions)
   - `FIRESTORE_DATABASE`, `FIRESTORE_COLLECTION_PREFIX` (optional)
   - `NOTIFY_RETRY_MAX_RETRIES`, `NOTIFY_RETRY_INITIAL_DELAY_SECONDS` (optional)
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS` (if using email)
   - `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE` (optional, `{title}` / `{message}` placeholders)
   - `LINE_NOTIFY_API_URL`, `LINE_MESSAGE_TEMPLATE` (optional)
   - GCP/WIF (see `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`):
     - `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
3. Register **Secrets** (credentials, masked in logs):
   - `TARGET_NAME` (AniList name-based check, if you prefer to keep it private)
   - If `NOTIFIER=email`:
     - `SMTP_FROM`, `SMTP_TO`, `SMTP_USER`, `SMTP_PASS`
   - If `NOTIFIER=line`:
     - `LINE_NOTIFY_TOKEN`

4. Trigger once manually from **Actions → Daily Credit Check → Run workflow**.

### Authentication Notes

- Keep credentials (passwords, tokens, personal addresses) in **GitHub Secrets** (never commit into repo files).
- Non-secret configuration (host names, ports, feature flags) should use **GitHub Variables**.
- The workflow passes both as runtime environment variables only.
- If credentials are invalid, the CLI exits with a clear configuration/notification error.


### SendGrid quick preset (for `NOTIFIER=email`)

Use these Secrets values when sending via SendGrid SMTP:

```text
NOTIFIER=email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Also set `SMTP_FROM` to a verified sender/domain in SendGrid.

