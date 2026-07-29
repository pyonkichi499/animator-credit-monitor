# 自動実行ガイド

Animator Credit Monitor を定期実行する方法をまとめます。実行前に `.env` を作成し、少なくとも監視対象と通知先を設定してください。

## 共通事項

- 推奨頻度は **1日1回**
- Bangumi ではページ間にデフォルト2秒の待機を入れる
- cron / systemd では `command -v uv` で確認した絶対パスを使用する
- `STATE_BACKEND=local` の場合、作業ディレクトリの `data/` を永続化する
- 複数ホスト・複数ジョブで実行する場合は `STATE_BACKEND=firestore` を推奨

## cron (Linux/macOS)

例: 毎日 09:00 に実行

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /absolute/path/to/uv run --locked --no-dev animator-credit-monitor check >> /path/to/logs/monitor.log 2>&1
```

日付別ログ:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /absolute/path/to/uv run --locked --no-dev animator-credit-monitor check >> /path/to/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

## タスクスケジューラ (Windows)

- プログラム: `uv`
- 引数: `run --locked --no-dev animator-credit-monitor check`
- 開始: リポジトリの絶対パス

## systemd timer (Linux)

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

`.github/workflows/daily-credit-check.yml` は次のタイミングで実行されます。

- schedule: 毎日 00:00 UTC（09:00 JST）
- `workflow_dispatch`: Actions 画面から手動実行

### 現在のworkflowが参照するGitHub Variables

必須:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `TARGET_BANGUMI_ID` または `TARGET_NAME`
- `NOTIFIER`: `console` または `email`
- `SMTP_PORT`: 通常は `587`

推奨:

- `STATE_BACKEND=firestore`
- `FIRESTORE_DATABASE=(default)`
- `NOTIFY_RETRY_MAX_RETRIES=2`
- `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

email 使用時:

- `SMTP_HOST`
- `SMTP_USE_TLS=true`
- 任意: `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE`

`TARGET_NAME` は公開したくない場合、Secret に登録できます。workflow は `secrets.TARGET_NAME` を優先します。

### GitHub Secrets

email 使用時:

- `SMTP_FROM`
- `SMTP_TO`
- `SMTP_USER`
- `SMTP_PASS`

`SMTP_USER` / `SMTP_PASS` を両方設定した場合だけ SMTP AUTH を実行します。Gmail は通常パスワードではなく App Password を使用してください。

### WIF

`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT` は、現在のworkflowでは `vars.*` を参照します。GitHub Secrets ではなく **GitHub Variables** に登録してください。

詳細は [`GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`](GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md) を参照してください。

### 初回確認

1. Actions → **Daily Credit Check** → **Run workflow**
2. `Authenticate to Google Cloud (WIF)` が成功する
3. `Run credit monitor` が設定エラーなしで開始する
4. Firestore の `runs` / `snapshots` を確認する
5. 差分がある場合は `events` / `deliveries` と通知結果を確認する

設定が空の場合に多いエラー:

- `Notifier type must be one of: console, email`: `NOTIFIER` が未設定
- `SMTP_PORT must be an integer`: workflow へ空文字が渡っているため `SMTP_PORT=587` が必要
- `GCP_PROJECT_ID is required when STATE_BACKEND=firestore`: `GCP_PROJECT_ID` Variable が未設定
- WIF step が skipped: WIF provider または service account Variable が未設定

## SendGrid SMTP 例

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

`SMTP_FROM` は SendGrid 側で認証済みの Sender Identity / Domain を使用します。
