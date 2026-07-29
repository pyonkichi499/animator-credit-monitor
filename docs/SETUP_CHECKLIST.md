# Setup Checklist

Checklist for operating with `GitHub Actions + Firestore + WIF + SMTP email`.

## 0. Prerequisites

- [ ] `gcloud` is available.
- [ ] `gh auth status` succeeds.
- [ ] A GCP project exists.
- [ ] Firestore Native mode can be enabled.
- [ ] You can configure GitHub Actions.

## 1. Monitoring Target

Set at least one:

- [ ] `TARGET_BANGUMI_ID`
- [ ] `TARGET_NAME`

When both are set, `check` without a source-only option checks both sources.

## 2. GitHub Variables

Firestore / WIF:

- [ ] `GCP_PROJECT_ID`
- [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER`
- [ ] `GCP_SERVICE_ACCOUNT`
- [ ] `STATE_BACKEND=firestore`
- [ ] `FIRESTORE_DATABASE=(default)` (optional)
- [ ] `FIRESTORE_COLLECTION_PREFIX` (optional)

Monitoring and notification:

- [ ] either `TARGET_BANGUMI_ID` or `TARGET_NAME`
- [ ] `NOTIFIER=email` (`console` is useful before testing email)
- [ ] `SMTP_PORT=587`
- [ ] `NOTIFY_RETRY_MAX_RETRIES=2`
- [ ] `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`

Email:

- [ ] `SMTP_HOST=smtp.gmail.com`
- [ ] `SMTP_USE_TLS=true`
- [ ] `EMAIL_SUBJECT_TEMPLATE` (optional)
- [ ] `EMAIL_BODY_TEMPLATE` (optional)

The current workflow reads the three GCP/WIF values from `vars.*`, so register them as Variables rather than Secrets.

## 3. GitHub Secrets

Email:

- [ ] `SMTP_FROM`
- [ ] `SMTP_TO`
- [ ] `SMTP_USER`
- [ ] `SMTP_PASS`

Optional:

- [ ] `TARGET_NAME` when the name should remain private; the Secret takes precedence over the Variable.

Gmail:

- [ ] Enable 2-Step Verification.
- [ ] Create an App Password.
- [ ] Store the App Password, not the normal account password, in `SMTP_PASS`.

## 4. Registration with GitHub CLI

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

Interactive Secret entry:

```bash
gh secret set SMTP_FROM
gh secret set SMTP_TO
gh secret set SMTP_USER
gh secret set SMTP_PASS
```

Verify:

```bash
gh variable list
gh secret list
```

## 5. GCP / WIF

- [ ] Create a Service Account for Firestore.
- [ ] Grant `roles/datastore.user`.
- [ ] Create a Workload Identity Pool / Provider.
- [ ] Grant the GitHub repository `roles/iam.workloadIdentityUser` on the Service Account.

See [`GCP_WIF_SETUP_FOR_GITHUB_ACTIONS_EN.md`](GCP_WIF_SETUP_FOR_GITHUB_ACTIONS_EN.md).

## 6. Firestore TTL

Configure `expiresAt` as the TTL field for:

- [ ] `runs`
- [ ] `events`
- [ ] `deliveries`

Do not configure TTL for `snapshots`.

## 7. First Run

- [ ] Actions → Daily Credit Check → Run workflow
- [ ] The WIF step is not skipped.
- [ ] `Run credit monitor` runs without configuration errors.
- [ ] `runs` and `snapshots` are created.
- [ ] When a diff exists, `events` and `deliveries` are created.
- [ ] Email is delivered.

## 8. Ongoing Operations

- [ ] The same diff is not repeatedly notified without reason.
- [ ] Failed deliveries are retried on the next run.
- [ ] TTL is working.
- [ ] GitHub Actions failure notifications are enabled.

## 9. Not Currently Implemented

- Concurrent-run locking
- Dedicated dead-letter collection
- Redelivery stopping based on `maxAttempts`
- Automated Secret Manager / Cloud Run Job migration
- Terraform configuration
