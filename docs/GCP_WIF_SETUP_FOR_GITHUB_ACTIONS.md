# GCP WIF Setup for GitHub Actions (Firestore)

対象:
- GitHub Actions から Firestore を使う
- Service Account JSON キーを GitHub Secrets に置かない
- Workload Identity Federation (WIF) を使う

前提:
- `gcloud` が使える
- GCP プロジェクト作成済み
- Firestore (Native mode) を有効化済み

この手順で作るもの:
- Service Account（Firestoreアクセス用）
- Workload Identity Pool
- GitHub OIDC Provider
- GitHub リポジトリからの impersonation 許可

スクリプト化:
- `scripts/gcp/setup_github_actions_wif.sh`
- `scripts/gcp/print_github_actions_wif_secrets.sh`
- `scripts/gcp/load_wif_env.template.sh`（ローカル用テンプレート）
- `scripts/gcp/run_wif_setup_with_local_env.sh`（ローカル env 読み込みラッパー）
- `scripts/github/actions.vars.template.sh`（シェル記法テンプレート / IDEハイライト向け）
- `scripts/github/actions.secrets.template.sh`（シェル記法テンプレート / IDEハイライト向け）
- `scripts/github/set_actions_config_from_local_env.sh`（`gh` CLI 登録）
- `scripts/gcp/secret_manager_sync_from_env.sh`（同じ secrets ファイルを Secret Manager に同期）
- `scripts/gcp/print_cloud_run_job_config_args.sh`（同じ vars/secrets ファイルから Cloud Run 引数を出力）
- `scripts/gcp/bootstrap_cloud_run_runtime_config_from_local_env.sh`（Cloud Run 移行用まとめ）

実値はすべて環境変数で渡す前提（認証情報や固有値を Git 管理ファイルに書かない）。

---

## 1. 変数を設定

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

または、スクリプト実行例:

```bash
cp scripts/gcp/load_wif_env.template.sh scripts/gcp/load_wif_env.local.sh
# scripts/gcp/load_wif_env.local.sh を編集（gitignore対象）
bash scripts/gcp/run_wif_setup_with_local_env.sh
# review-first wrapper (preview only)
bash scripts/github/bootstrap_gcp_wif_and_actions_config.sh
# execute after review
APPLY=1 bash scripts/github/bootstrap_gcp_wif_and_actions_config.sh
```

---

## 2. 手動実行したい場合（参考）

以下はスクリプトの中身と同等の `gcloud` コマンドです。基本はスクリプト利用を推奨します。

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Animator Credit Monitor (GitHub Actions)"
```

Firestore へのアクセス権（最小構成寄り）

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

補足:
- Firestore のドキュメント read/write 用に `roles/datastore.user` を使用
- さらに絞りたい場合は後でカスタムロール化

---

## 3. Workload Identity Pool / Provider を作成

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

補足:
- `attribute-condition` で repository / branch を制限
- PR 実行や複数ブランチを許可したい場合は条件を調整

---

## 4. GitHub OIDC Principal に Service Account 利用権限を付与

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

---

## 5. GitHub Actions Secrets に設定する値

GitHub Repository → `Settings` → `Secrets and variables` → `Actions`

必須（GCP/WIF）:
- GitHub **Variables** に登録:
  - `GCP_PROJECT_ID`
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_SERVICE_ACCOUNT`

値の確認:

```bash
bash scripts/gcp/print_github_actions_wif_secrets.sh
```

推奨:
- 非秘匿値は GitHub **Variables**
- パスワード/トークン/個人メールなどは GitHub **Secrets**

テンプレート:
- `scripts/github/actions.vars.template.sh`
- `scripts/github/actions.secrets.template.sh`
- 旧まとめ版: `templates/gmail_github_secrets.template.txt`

`gh` CLI で登録する例:

```bash
cp scripts/github/actions.vars.template.sh scripts/github/actions.vars.local.sh
cp scripts/github/actions.secrets.template.sh scripts/github/actions.secrets.local.sh
# 2ファイルを編集（gitignore対象）
bash scripts/github/set_actions_config_from_local_env.sh        # preview only
APPLY=1 bash scripts/github/set_actions_config_from_local_env.sh
```

Cloud Run へ移行する時も、同じローカルファイルを流用可能:

```bash
export PROJECT_ID="your-gcp-project-id"
bash scripts/gcp/bootstrap_cloud_run_runtime_config_from_local_env.sh
```

上記で:
- `actions.secrets.local.sh` の値を GCP Secret Manager に同期
- Cloud Run Job の `--set-env-vars` / `--set-secrets` 引数を出力

---

## 6. Firestore TTL（30日）を設定

このアプリは以下のフィールド名を使う:
- `runs.expiresAt`
- `events.expiresAt`
- `deliveries.expiresAt`

TTL の有効化は GCP コンソールから行うのが簡単です。

手順（コンソール）:
1. Firestore → `TTL`
2. コレクション `runs` を選択し、TTL field に `expiresAt`
3. `events` も同様
4. `deliveries` も同様

`snapshots` は TTL を設定しない（比較基準のため）。

---

## 7. Gmail SMTP の注意点

- Gmail SMTP を使う場合、通常の Google アカウントパスワードではなく **App Password** を使う
- 2段階認証を有効化して App Password を発行する
- `SMTP_PASS` には App Password（16文字）を設定する

推奨設定:
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USE_TLS=true`
- `SMTP_USER=<your gmail address>`
- `SMTP_FROM=<same gmail address>`

---

## 8. 動作確認

1. GitHub Secrets 設定
2. `Daily Credit Check` を手動実行
3. Firestore に `runs` / `events` / `deliveries` / `snapshots` が作成されることを確認
4. `partial_failure` 時は Actions が失敗（赤）になり、Firestore に状態が残ることを確認
