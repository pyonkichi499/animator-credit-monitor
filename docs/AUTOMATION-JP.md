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
