# Automation Guide

This guide describes how to run Animator Credit Monitor on a schedule. Create `.env` and configure at least one monitoring target and a notifier before enabling automation.

## Common Notes

- Recommended frequency: **once per day**
- Bangumi waits two seconds between paginated requests by default.
- For cron/systemd, use the absolute path returned by `command -v uv`.
- With `STATE_BACKEND=local`, keep the working directory's `data/` directory persistent.
- Prefer `STATE_BACKEND=firestore` when multiple hosts or jobs may run the monitor.

## cron (Linux/macOS)

Run every day at 09:00:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /absolute/path/to/uv run --locked --no-dev animator-credit-monitor check >> /path/to/logs/monitor.log 2>&1
```

Daily log files:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /absolute/path/to/uv run --locked --no-dev animator-credit-monitor check >> /path/to/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

## Task Scheduler (Windows)

- Program: `uv`
- Arguments: `run --locked --no-dev animator-credit-monitor check`
- Start in: the repository's absolute path

## systemd Timer (Linux)

`~/.config/systemd/user/animator-credit-monitor.service`:

```ini
[Unit]
Description=Animator Credit Monitor

[Service]
Type=oneshot
WorkingDirectory=/path/to/animator-credit-monitor
ExecStart=/absolute/path/to/uv run --locked --no-dev animator-credit-monitor check
```

`~/.config/systemd/user/animator-credit-monitor.timer`:

```ini
[Unit]
Description=Run Animator Credit Monitor daily

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now animator-credit-monitor.timer
```

## GitHub Actions

`.github/workflows/daily-credit-check.yml` runs:

- on schedule at 00:00 UTC (09:00 JST)
- manually through `workflow_dispatch`

### GitHub Variables Used by the Current Workflow

Required:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- either `TARGET_BANGUMI_ID` or `TARGET_NAME`
- `NOTIFIER`: `console` or `email`
- `SMTP_PORT`: normally `587`

Recommended:

- `STATE_BACKEND=firestore`
- `FIRESTORE_DATABASE=(default)`
- `NOTIFY_RETRY_MAX_RETRIES=2`
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

For email:

- `SMTP_HOST`
- `SMTP_USE_TLS=true`
- optional: `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE`

`TARGET_NAME` may be stored as a Secret when it should not be public; the workflow prefers `secrets.TARGET_NAME`.

### GitHub Secrets

For email:

- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_USER`
- `SMTP_PASS`

SMTP AUTH is used only when both `SMTP_USER` and `SMTP_PASS` are set. For Gmail, use an App Password instead of the normal account password.

### WIF

The current workflow reads `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and `GCP_SERVICE_ACCOUNT` from `vars.*`. Register them as **GitHub Variables**, not GitHub Secrets.

See [`GCP_WIF_SETUP_FOR_GITHUB_ACTIONS_EN.md`](GCP_WIF_SETUP_FOR_GITHUB_ACTIONS_EN.md).

### First Validation

1. Actions → **Daily Credit Check** → **Run workflow**
2. Confirm `Authenticate to Google Cloud (WIF)` succeeds.
3. Confirm `Run credit monitor` starts without a configuration error.
4. Inspect Firestore `runs` / `snapshots`.
5. When a diff exists, inspect `events` / `deliveries` and the notification result.

Common errors caused by empty configuration:

- `Notifier type must be one of: console, email`: `NOTIFIER` is missing.
- `SMTP_PORT must be an integer`: the workflow passed an empty value; set `SMTP_PORT=587`.
- `GCP_PROJECT_ID is required when STATE_BACKEND=firestore`: the `GCP_PROJECT_ID` Variable is missing.
- WIF step is skipped: the provider or service-account Variable is missing.

## SendGrid SMTP Example

Variables:

```text
NOTIFIER=email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
```

Secrets:

```text
SMTP_FROM=verified-sender@example.com
SMTP_TO=destination@example.com
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Use a sender identity or domain verified by SendGrid for `SMTP_FROM`.
