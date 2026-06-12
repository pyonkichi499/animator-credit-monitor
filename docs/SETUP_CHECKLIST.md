# Setup Checklist (For Safe Operations)

Purpose:
- Safely set up `GitHub Actions + Firestore + WIF + Gmail SMTP`
- Keep credentials out of Git version control
- Proceed with reviewable steps rather than relying on a single "run-it-all" script

Approach (Recommended)
- GCP resource creation: `Terraform` (recommended)
- Alternative: Run `gcloud` commands manually (reviewing each command as you go)
- GitHub configuration: Explicitly register `Variables` / `Secrets` using the `gh` CLI

Notes:
- Existing `scripts/` may be used, but are not required
- This checklist assumes you will proceed manually while reviewing each step

---

## 0. Prerequisites

- [ ] `gcloud` is available
- [ ] `gh` is available (verify with `gh auth status`)
- [ ] The target GitHub repository has `Actions` permissions enabled
- [ ] A target GCP project exists
- [ ] Using Firestore (Native mode) is acceptable

---

## 1. Organize Values (Decide in Advance)

Non-sensitive (GitHub Variables candidates)
- [ ] `GCP_PROJECT_ID`
- [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER` (after WIF creation)
- [ ] `GCP_SERVICE_ACCOUNT` (after WIF creation)
- [ ] `STATE_BACKEND=firestore`
- [ ] `NOTIFIER=email` (or `NOTIFIERS=email,line`)
- [ ] `SMTP_HOST=smtp.gmail.com`
- [ ] `SMTP_PORT=587`
- [ ] `SMTP_USE_TLS=true`
- [ ] `NOTIFY_RETRY_MAX_RETRIES=2`
- [ ] `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`
- [ ] `FIRESTORE_DATABASE=(default)` (optional)
- [ ] `FIRESTORE_COLLECTION_PREFIX` (optional)

Sensitive (GitHub Secrets candidates)
- [ ] `SMTP_PASS` (Gmail App Password)
- [ ] `SMTP_USER` (treat as Secret if needed)
- [ ] `SMTP_FROM`
- [ ] `SMTP_TO`
- [ ] `TARGET_NAME` (if you prefer not to expose it)
- [ ] `LINE_NOTIFY_TOKEN` (if used)

---

## 2. GCP Resource Creation (Terraform Recommended)

### 2-1. Resources to Manage with Terraform (Recommended)

- [ ] Service Account (for Firestore access)
- [ ] IAM role binding (`roles/datastore.user`)
- [ ] Workload Identity Pool
- [ ] GitHub OIDC Provider
- [ ] `roles/iam.workloadIdentityUser` binding to the Service Account

### 2-2. Steps When Using Terraform (Recommended)

- [ ] Review `terraform plan` before running `apply`
- [ ] Decide where to store tfstate (local or remote backend)
- [ ] Do not commit sensitive values in `.tfvars` to Git (or use Terraform Cloud Variables)
- [ ] After creation, record the following:
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - [ ] `GCP_SERVICE_ACCOUNT`

### 2-3. Using `gcloud` Instead of Terraform (Alternative)

- [ ] `gcloud auth login`
- [ ] `gcloud config set project <PROJECT_ID>`
- [ ] Review and execute each `gcloud` command one at a time
- [ ] Save execution logs/output (for reproducibility)

Reference:
- `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`

---

## 3. Firestore Initial Setup (GCP Console)

- [ ] Enable Firestore in Native mode (if not already done)
- [ ] Configure TTL (on the `expiresAt` field)
  - [ ] `runs`
  - [ ] `events`
  - [ ] `deliveries`
- [ ] Do not configure TTL for `snapshots`

---

## 4. Gmail SMTP Preparation

- [ ] Enable 2-Step Verification on your Google account
- [ ] Create an App Password
- [ ] Save the App Password as `SMTP_PASS` (the value to store in GitHub Secrets)
- [ ] Use the same Gmail address for both `SMTP_FROM` and `SMTP_USER`

---

## 5. Register GitHub Actions Variables / Secrets

### 5-1. Registration Method (Recommended)

- [ ] Register Variables using `gh variable set ...`
- [ ] Register Secrets using `gh secret set ...`
- [ ] Review registration commands before executing (check copy-pasted content)
- [ ] When using helper scripts, first verify in preview-only mode (the default)
- [ ] Only add `APPLY=1` when you are ready to apply changes

### 5-2. Verify Registration

- [ ] Verify Variables with `gh variable list`
- [ ] Verify Secret names with `gh secret list` (values are not displayed)
- [ ] Make a final decision on whether `TARGET_NAME` should be a Variable or a Secret

Note:
- In this repository, the `workflow` supports both `vars.*` and `secrets.*` (with priority depending on the item)

---

## 6. First Run (GitHub Actions)

- [ ] `Actions` → `Daily Credit Check` → `Run workflow`
- [ ] `Authenticate to Google Cloud (WIF)` succeeds
- [ ] `Run credit monitor` executes
- [ ] Check logs on failure (WIF / Firestore / SMTP)

---

## 7. Post-First-Run Verification (Firestore / Email)

- [ ] Firestore collections are created
  - [ ] `runs`
  - [ ] `events`
  - [ ] `deliveries`
  - [ ] `snapshots`
- [ ] `runs.status` is as expected (`success` or `partial_failure`)
- [ ] Gmail notification is received (when there are diffs)
- [ ] In case of `partial_failure`, failed state remains in `deliveries`

---

## 8. Operational Verification (Following Days)

- [ ] Failed `deliveries` are retried on the next run
- [ ] TTL for `runs/events/deliveries` is functioning correctly
- [ ] No excessive unintended duplicate notifications are occurring

---

## 9. Future (When Migrating to Cloud Run)

- [ ] Inventory the values stored in GitHub Variables/Secrets
- [ ] Move `Secrets` to Secret Manager (`SMTP_PASS`, `LINE_NOTIFY_TOKEN`, etc.)
- [ ] Review and configure Cloud Run Job `--set-env-vars` / `--set-secrets`
- [ ] Continue using WIF (if GitHub-to-GCP integration is still needed)

Note:
- The current codebase is structured with Cloud Run migration in mind (Firestore + Outbox)

---

## 10. Not Doing Today (Can Be Deferred)

- [ ] Terraform migration (do it later if not yet done)
- [ ] Monitoring dashboard (BigQuery / Looker Studio)
- [ ] Cloud Run migration
- [ ] Full migration to Secret Manager
