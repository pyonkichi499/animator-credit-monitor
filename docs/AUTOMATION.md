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
2. Register secrets used by the workflow:
   - Required for monitoring target:
     - `TARGET_NAME` (AniList name-based check)
     - `TARGET_BANGUMI_ID` (optional if you also monitor Bangumi)
   - Required notifier selector:
     - `NOTIFIER` (`console`, `email`, or `line`)
     - `NOTIFIERS` (optional multi-destination, e.g. `email,line`)
   - If `NOTIFIER=email`:
     - `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_TO`
     - `SMTP_USER`, `SMTP_PASS` (if authentication is required)
     - `SMTP_USE_TLS` (e.g., `true`)
     - `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE` (optional, `{title}` / `{message}` placeholders)
   - If `NOTIFIER=line`:
     - `LINE_NOTIFY_TOKEN`
     - `LINE_NOTIFY_API_URL` (optional; defaults to LINE Notify compatible endpoint)
     - `LINE_MESSAGE_TEMPLATE` (optional, `{title}` / `{message}` placeholders)

3. Trigger once manually from **Actions → Daily Credit Check → Run workflow**.

### Authentication Notes

- Keep all credentials in **GitHub Secrets** (never commit into repo files).
- The workflow passes credentials as runtime environment variables only.
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

