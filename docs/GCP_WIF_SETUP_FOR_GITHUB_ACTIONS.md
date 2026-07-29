# GitHub Actions 向け GCP WIF セットアップ

GitHub Actions から Service Account JSON キーを使わず Firestore へ接続する手順です。

このリポジトリには WIF リソース作成スクリプトは含まれていません。以下のコマンドを確認し、手動または自分の IaC へ移植して実行してください。

## 1. 値を決める

```bash
PROJECT_ID="your-project-id"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
POOL_ID="github-pool"
PROVIDER_ID="github-provider"
SA_NAME="animator-credit-monitor"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GITHUB_OWNER="your-owner"
GITHUB_REPO="animator-credit-monitor"
GITHUB_REF="refs/heads/develop"
```

現在の定期workflowは `develop` で動いています。main へ移行する場合は provider の条件も合わせて変更してください。

## 2. API と Firestore

```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  firestore.googleapis.com \
  --project="$PROJECT_ID"
```

Firestore は GCP Console から Native mode で作成します。location は後から変更できないため事前に確認してください。

## 3. Service Account

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Animator Credit Monitor (GitHub Actions)"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

## 4. Workload Identity Pool / Provider

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub OIDC Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${GITHUB_OWNER}/${GITHUB_REPO}' && assertion.ref=='${GITHUB_REF}'"
```

provider resource name:

```bash
WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)')"
printf '%s\n' "$WIF_PROVIDER"
```

## 5. Service Account impersonation

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

## 6. GitHub Variables

現在の `.github/workflows/daily-credit-check.yml` は次を `vars.*` から参照します。

```bash
gh variable set GCP_PROJECT_ID --body "$PROJECT_ID"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$WIF_PROVIDER"
gh variable set GCP_SERVICE_ACCOUNT --body "$SA_EMAIL"
```

これらを Secrets にだけ登録しても WIF step は実行されません。

## 7. Firestore TTL

GCP Console の Firestore → TTL で `expiresAt` を設定:

- `runs`
- `events`
- `deliveries`

`snapshots` は比較基準なので TTL なしです。

## 8. 動作確認

1. GitHub Variables に WIF 3項目を登録
2. `TARGET_BANGUMI_ID` または `TARGET_NAME` を登録
3. `NOTIFIER`, `SMTP_PORT` と必要なSMTP設定を登録
4. Actions → Daily Credit Check → Run workflow
5. WIF step が成功することを確認
6. Firestore に `runs` が作成されることを確認

WIF step が skipped の場合、`GCP_WORKLOAD_IDENTITY_PROVIDER` または `GCP_SERVICE_ACCOUNT` Variable が空です。
