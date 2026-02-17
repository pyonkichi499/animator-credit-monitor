# 自動実行ガイド

## cron (Linux/macOS)

### セットアップ

1. crontabエディタを開く:

```bash
crontab -e
```

2. 毎日1回のチェックを追加（例: 毎日 9:00）:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /path/to/.rye/shims/rye run animator-credit-monitor check >> /path/to/logs/monitor.log 2>&1
```

### 推奨実行頻度

- **1日1回** を推奨。対象サイトへの過剰な負荷を避けるため
- Bangumi と AniList はコミュニティ運営のデータベース。サーバーリソースへの配慮を忘れずに

### ログ出力

日付ごとにログローテーション:

```cron
0 9 * * * cd /path/to/animator-credit-monitor && /path/to/.rye/shims/rye run animator-credit-monitor check >> /path/to/logs/monitor_$(date +\%Y\%m\%d).log 2>&1
```

## タスクスケジューラ (Windows)

1. タスクスケジューラを開く
2. 「基本タスクの作成」を選択
3. トリガーを「毎日」に設定
4. 操作を「プログラムの開始」に設定:
   - プログラム: `rye`
   - 引数: `run animator-credit-monitor check`
   - 開始: `C:\path\to\animator-credit-monitor`

## systemd タイマー (Linux)

### サービスファイル (`/etc/systemd/user/animator-monitor.service`)

```ini
[Unit]
Description=Animator Credit Monitor

[Service]
Type=oneshot
WorkingDirectory=/path/to/animator-credit-monitor
ExecStart=/path/to/.rye/shims/rye run animator-credit-monitor check
```

### タイマーファイル (`/etc/systemd/user/animator-monitor.timer`)

```ini
[Unit]
Description=アニメーター作画クレジット検知を毎日実行

[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 有効化

```bash
systemctl --user enable --now animator-monitor.timer
```

## GitHub Actions（定期実行）

このリポジトリには `.github/workflows/daily-credit-check.yml` を用意している。

### セットアップ

1. GitHub リポジトリの **Settings → Secrets and variables → Actions** を開く。
2. ワークフローで使う Secrets を登録する:
   - 監視対象として必要:
     - `TARGET_NAME`（AniList の name ベース監視）
     - `TARGET_BANGUMI_ID`（Bangumi も監視する場合は設定）
   - 通知先選択:
     - `NOTIFIER`（`console` / `email` / `line`）
     - `NOTIFIERS`（任意。複数通知先。例: `email,line`）
   - `NOTIFIER=email` の場合:
     - `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_TO`
     - `SMTP_USER`, `SMTP_PASS`（認証が必要な場合）
     - `SMTP_USE_TLS`（例: `true`）
     - `EMAIL_SUBJECT_TEMPLATE`, `EMAIL_BODY_TEMPLATE`（任意。`{title}` / `{message}` プレースホルダ対応）
   - `NOTIFIER=line` の場合:
     - `LINE_NOTIFY_TOKEN`
     - `LINE_NOTIFY_API_URL`（任意。未設定時は互換エンドポイントを使用）
     - `LINE_MESSAGE_TEMPLATE`（任意。`{title}` / `{message}` プレースホルダ対応）

3. **Actions → Daily Credit Check → Run workflow** で手動実行し、初回動作確認を行う。

### 認証情報の扱い

- 認証情報は必ず **GitHub Secrets** に保存する（リポジトリへコミットしない）。
- ワークフローでは実行時の環境変数としてのみ注入される。
- 認証情報が不正な場合はCLIが設定/通知エラーを明示して終了する。


### SendGrid かんたん設定（`NOTIFIER=email` 用）

SendGrid SMTP で送る場合は、Secrets を次の値で設定するとよい。

```text
NOTIFIER=email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

`SMTP_FROM` は SendGrid 側で認証済みの送信元（Sender Identity / Domain Authentication）を使うこと。

