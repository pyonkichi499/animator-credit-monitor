# GCP WIF Setup for GitHub Actions (Firestore)

Scope:
- Use Firestore from GitHub Actions
- Avoid placing Service Account JSON keys in GitHub Secrets
- Use Workload Identity Federation (WIF)

Prerequisites:
- `gcloud` is available
- GCP project already created
- Firestore (Native mode) already enabled

What this guide creates:
- Service Account (for Firestore access)
- Workload Identity Pool
- GitHub OIDC Provider
- Impersonation permission from the GitHub repository

Scripts:
- `scripts/gcp/setup_github_actions_wif.sh`
- `scripts/gcp/print_github_actions_wif_secrets.sh`
- `scripts/gcp/load_wif_env.template.sh` (local environment template)
- `scripts/gcp/run_wif_setup_with_local_env.sh` (local env loading wrapper)
- `scripts/github/actions.vars.template.sh` (shell syntax template / for IDE highlighting)
- `scripts/github/actions.secrets.template.sh` (shell syntax template / for IDE highlighting)
- `scripts/github/set_actions_config_from_local_env.sh` (`gh` CLI registration)
- `scripts/gcp/secret_manager_sync_from_env.sh` (sync the same secrets file to Secret Manager)
- `scripts/gcp/print_cloud_run_job_config_args.sh` (output Cloud Run arguments from the same vars/secrets files)
- `scripts/gcp/bootstrap_cloud_run_runtime_config_from_local_env.sh` (all-in-one for Cloud Run migration)

All actual values are passed via environment variables (credentials and project-specific values are never stored in Git-managed files).

---

## 1. Set Variables

```bash
PROJECT_ID="animator-credit-monitor"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
POOL_ID="github-pool"
PROVIDER_ID="github-provider"
SA_NAME="animator-credit-monitor"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# GitHub repository (owner/repo)
GITHUB_OWNER="your-github-owner"
GITHUB_REPO="your-repo"
GITHUB_REF="refs/heads/main"
```

Or, using the scripts:

```bash
cp scripts/gcp/load_wif_env.template.sh scripts/gcp/load_wif_env.local.sh
# Edit scripts/gcp/load_wif_env.local.sh (gitignored)
bash scripts/gcp/run_wif_setup_with_local_env.sh
# review-first wrapper (preview only)
bash scripts/github/bootstrap_gcp_wif_and_actions_config.sh
# execute after review
APPLY=1 bash scripts/github/bootstrap_gcp_wif_and_actions_config.sh
```

---

## 2. Manual Execution (Reference)

The following `gcloud` commands are equivalent to what the scripts do. Using the scripts is generally recommended.

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Animator Credit Monitor (GitHub Actions)"
```

Firestore access permissions (minimal configuration)

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

Notes:
- `roles/datastore.user` is used for Firestore document read/write
- If further restriction is needed, consider creating a custom role later

---

## 3. Create Workload Identity Pool / Provider

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

Notes:
- `attribute-condition` restricts access by repository / branch
- Adjust the condition if you want to allow PR runs or multiple branches

---

## 4. Grant Service Account Usage Permission to GitHub OIDC Principal

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

---

## 5. Values to Set in GitHub Actions Secrets

GitHub Repository -> `Settings` -> `Secrets and variables` -> `Actions`

Required (GCP/WIF):
- Register as GitHub **Variables**:
  - `GCP_PROJECT_ID`
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_SERVICE_ACCOUNT`

Verify the values:

```bash
bash scripts/gcp/print_github_actions_wif_secrets.sh
```

Recommended:
- Non-sensitive values go in GitHub **Variables**
- Passwords / tokens / personal email addresses go in GitHub **Secrets**

Templates:
- `scripts/github/actions.vars.template.sh`
- `scripts/github/actions.secrets.template.sh`
- Legacy combined version: `templates/gmail_github_secrets.template.txt`

Example of registering via `gh` CLI:

```bash
cp scripts/github/actions.vars.template.sh scripts/github/actions.vars.local.sh
cp scripts/github/actions.secrets.template.sh scripts/github/actions.secrets.local.sh
# Edit both files (gitignored)
bash scripts/github/set_actions_config_from_local_env.sh        # preview only
APPLY=1 bash scripts/github/set_actions_config_from_local_env.sh
```

The same local files can be reused when migrating to Cloud Run:

```bash
export PROJECT_ID="your-gcp-project-id"
bash scripts/gcp/bootstrap_cloud_run_runtime_config_from_local_env.sh
```

The above will:
- Sync values from `actions.secrets.local.sh` to GCP Secret Manager
- Output `--set-env-vars` / `--set-secrets` arguments for the Cloud Run Job

---

## 6. Configure Firestore TTL (30 days)

This application uses the following field names:
- `runs.expiresAt`
- `events.expiresAt`
- `deliveries.expiresAt`

The easiest way to enable TTL is through the GCP Console.

Steps (Console):
1. Go to Firestore -> `TTL`
2. Select the `runs` collection and set the TTL field to `expiresAt`
3. Do the same for `events`
4. Do the same for `deliveries`

Do not set TTL on `snapshots` (it serves as the comparison baseline).

---

## 7. Gmail SMTP Notes

- When using Gmail SMTP, use an **App Password** instead of a regular Google account password
- Enable 2-Step Verification and generate an App Password
- Set `SMTP_PASS` to the App Password (16 characters)

Recommended settings:
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USE_TLS=true`
- `SMTP_USER=<your gmail address>`
- `SMTP_FROM=<same gmail address>`

---

## 8. Verification

1. Configure GitHub Secrets
2. Manually trigger `Daily Credit Check`
3. Verify that `runs` / `events` / `deliveries` / `snapshots` are created in Firestore
4. Verify that on `partial_failure`, the Actions run fails (red) and the state is persisted in Firestore
