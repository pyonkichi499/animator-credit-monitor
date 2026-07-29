# セットアップチェックリスト

`GitHub Actions + Firestore + WIF + SMTP email` で運用するための確認項目です。

## 0. 前提

- [ ] `gcloud` が使用できる
- [ ] `gh auth status` が成功する
- [ ] GCP プロジェクトがある
- [ ] Firestore Native mode を有効化できる
- [ ] GitHub Actions を設定できる

## 1. 監視対象

少なくとも一方:

- [ ] `TARGET_BANGUMI_ID`
- [ ] `TARGET_NAME`

両方を設定すると、オプションなしの `check` で両ソースを確認します。

## 2. GitHub Variables

Firestore / WIF:

- [ ] `GCP_PROJECT_ID`
- [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER`
- [ ] `GCP_SERVICE_ACCOUNT`
- [ ] `STATE_BACKEND=firestore`
- [ ] `FIRESTORE_DATABASE=(default)`（省略可）
- [ ] `FIRESTORE_COLLECTION_PREFIX`（省略可）

監視・通知:

- [ ] `TARGET_BANGUMI_ID` または `TARGET_NAME`
- [ ] `NOTIFIER=email`（通知テスト前は `console` でも可）
- [ ] `SMTP_PORT=587`
- [ ] `NOTIFY_RETRY_MAX_RETRIES=2`
- [ ] `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

email:

- [ ] `SMTP_HOST=smtp.gmail.com`
- [ ] `SMTP_USE_TLS=true`
- [ ] `EMAIL_SUBJECT_TEMPLATE`（任意）
- [ ] `EMAIL_BODY_TEMPLATE`（任意）

現在のworkflowは GCP/WIF の3項目を `vars.*` から読むため、Secrets ではなく Variables に登録します。

## 3. GitHub Secrets

email:

- [ ] `SMTP_FROM`
- [ ] `SMTP_TO`
- [ ] `SMTP_USER`
- [ ] `SMTP_PASS`

任意:

- [ ] `TARGET_NAME`（名前を公開したくない場合。Secret が Variable より優先）

Gmail:

- [ ] 2段階認証を有効化
- [ ] App Password を作成
- [ ] 通常パスワードではなく App Password を `SMTP_PASS` に登録

## 4. GitHub CLI で登録する例

Variables:

```bash
gh variable set GCP_PROJECT_ID --body "your-project-id"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
gh variable set GCP_SERVICE_ACCOUNT --body "animator-credit-monitor@your-project-id.iam.gserviceaccount.com"
gh variable set STATE_BACKEND --body "firestore"
gh variable set TARGET_BANGUMI_ID --body "12345"
gh variable set NOTIFIER --body "email"
gh variable set SMTP_HOST --body "smtp.gmail.com"
gh variable set SMTP_PORT --body "587"
gh variable set SMTP_USE_TLS --body "true"
```

Secrets は対話入力を使う例:

```bash
gh secret set SMTP_FROM
gh secret set SMTP_TO
gh secret set SMTP_USER
gh secret set SMTP_PASS
```

確認:

```bash
gh variable list
gh secret list
```

## 5. GCP / WIF

- [ ] Firestore アクセス用 Service Account を作成
- [ ] Service Account に `roles/datastore.user` を付与
- [ ] Workload Identity Pool / Provider を作成
- [ ] GitHub repository から Service Account への `roles/iam.workloadIdentityUser` を付与

詳細は [`GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`](GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md)。

## 6. Firestore TTL

`expiresAt` を TTL field に設定:

- [ ] `runs`
- [ ] `events`
- [ ] `deliveries`

`snapshots` には TTL を設定しません。

## 7. 初回実行

- [ ] Actions → Daily Credit Check → Run workflow
- [ ] WIF step が skipped されない
- [ ] `Run credit monitor` が設定エラーなしで実行される
- [ ] `runs` と `snapshots` が作成される
- [ ] 差分がある場合は `events` / `deliveries` が作成される
- [ ] email が届く

## 8. 継続運用

- [ ] 翌日以降、同じ差分が過剰通知されない
- [ ] 失敗した delivery が次回実行で再送される
- [ ] TTL が機能する
- [ ] GitHub Actions の失敗通知を有効化する

## 9. 現在未実装

- 同時実行の排他制御
- dead-letter 専用コレクション
- `maxAttempts` による再送停止
- Secret Manager / Cloud Run Job への自動移行
- Terraform 構成
