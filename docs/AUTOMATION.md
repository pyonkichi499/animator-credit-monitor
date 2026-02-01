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
