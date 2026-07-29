# GCP WIF Setup for GitHub Actions

This guide configures keyless Firestore access from GitHub Actions without storing a Service Account JSON key.

This repository does not include scripts that create WIF resources. Review the commands below and run them manually or translate them into your own IaC.

## 1. Choose Values

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

The current scheduled workflow runs from `develop`. If you move it to `main`, update the provider condition accordingly.

## 2. APIs and Firestore

```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  firestore.googleapis.com \
  --project="$PROJECT_ID"
```

Create Firestore in Native mode through the GCP Console. Review the location before creation because it cannot be changed later.

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

Get the provider resource name:

```bash
WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)')"
printf '%s\n' "$WIF_PROVIDER"
```

## 5. Service Account Impersonation

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

## 6. GitHub Variables

The current `.github/workflows/daily-credit-check.yml` reads these values from `vars.*`:

```bash
gh variable set GCP_PROJECT_ID --body "$PROJECT_ID"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$WIF_PROVIDER"
gh variable set GCP_SERVICE_ACCOUNT --body "$SA_EMAIL"
```

Registering them only as Secrets does not activate the WIF step.

## 7. Firestore TTL

In GCP Console → Firestore → TTL, set `expiresAt` for:

- `runs`
- `events`
- `deliveries`

Do not enable TTL for `snapshots`.

## 8. Verification

1. Register the three WIF Variables.
2. Register either `TARGET_BANGUMI_ID` or `TARGET_NAME`.
3. Register `NOTIFIER`, `SMTP_PORT`, and any required SMTP settings.
4. Actions → Daily Credit Check → Run workflow.
5. Confirm that the WIF step succeeds.
6. Confirm that a Firestore `runs` document is created.

If the WIF step is skipped, `GCP_WORKLOAD_IDENTITY_PROVIDER` or `GCP_SERVICE_ACCOUNT` is empty.
