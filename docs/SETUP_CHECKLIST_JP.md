# セットアップチェックリスト（安全運用向け）

目的:
- `GitHub Actions + Firestore + WIF + Gmail SMTP` を安全にセットアップする
- 認証情報を Git 管理下に置かない
- 「一発スクリプト任せ」ではなく、レビュー可能な手順で進める

方針（推奨）
- GCP リソース作成: `Terraform`（推奨）
- 代替: `gcloud` コマンドを手で実行（コマンド内容を確認しながら）
- GitHub 設定: `gh` CLI で `Variables` / `Secrets` を明示登録

補足:
- 既存の `scripts/` は使ってもよいが、必須ではない
- このチェックリストは「レビューしながら手で進める」前提

---

## 0. 事前確認

- [ ] `gcloud` が使える
- [ ] `gh` が使える（`gh auth status` で確認）
- [ ] 対象 GitHub リポジトリに `Actions` 権限がある
- [ ] 対象 GCP プロジェクトがある
- [ ] Firestore (Native mode) を使う前提で問題ない

---

## 1. 値の整理（先に決める）

非秘匿（GitHub Variables 候補）
- [ ] `GCP_PROJECT_ID`
- [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER`（WIF作成後）
- [ ] `GCP_SERVICE_ACCOUNT`（WIF作成後）
- [ ] `STATE_BACKEND=firestore`
- [ ] `NOTIFIER=email`（または `NOTIFIERS=email,line`）
- [ ] `SMTP_HOST=smtp.gmail.com`
- [ ] `SMTP_PORT=587`
- [ ] `SMTP_USE_TLS=true`
- [ ] `NOTIFY_RETRY_MAX_RETRIES=2`
- [ ] `NOTIFY_RETRY_INITIAL_DELAY_SECONDS=60`
- [ ] `FIRESTORE_DATABASE=(default)`（任意）
- [ ] `FIRESTORE_COLLECTION_PREFIX`（任意）

秘匿（GitHub Secrets 候補）
- [ ] `SMTP_PASS`（Gmail App Password）
- [ ] `SMTP_USER`（必要に応じて Secret 扱い）
- [ ] `SMTP_FROM`
- [ ] `SMTP_TO`
- [ ] `TARGET_NAME`（公開したくない場合）
- [ ] `LINE_NOTIFY_TOKEN`（使う場合）

---

## 2. GCP リソース作成（Terraform 推奨）

### 2-1. Terraform で管理する対象（推奨）

- [ ] Service Account（Firestoreアクセス用）
- [ ] IAM ロール付与（`roles/datastore.user`）
- [ ] Workload Identity Pool
- [ ] GitHub OIDC Provider
- [ ] Service Account への `roles/iam.workloadIdentityUser` バインディング

### 2-2. Terraform を使う場合の進め方（推奨）

- [ ] `terraform plan` をレビューしてから `apply`
- [ ] tfstate の保存先を決める（ローカル or remote backend）
- [ ] 機密値は `.tfvars` を git 管理しない（または Terraform Cloud Variables）
- [ ] 作成後、以下を控える:
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - [ ] `GCP_SERVICE_ACCOUNT`

### 2-3. Terraform を使わず `gcloud` でやる場合（代替）

- [ ] `gcloud auth login`
- [ ] `gcloud config set project <PROJECT_ID>`
- [ ] 実行する `gcloud` コマンドを1つずつレビューして実行
- [ ] 実行ログ/出力を保存しておく（再現用）

参照:
- `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`

---

## 3. Firestore 初期設定（GCP Console）

- [ ] Firestore を Native mode で有効化（未実施なら）
- [ ] TTL を設定（`expiresAt` フィールド）
  - [ ] `runs`
  - [ ] `events`
  - [ ] `deliveries`
- [ ] `snapshots` は TTL を設定しない

---

## 4. Gmail SMTP 準備

- [ ] Google アカウントで 2段階認証を有効化
- [ ] App Password を作成
- [ ] App Password を `SMTP_PASS` に保存（GitHub Secret に入れる値）
- [ ] `SMTP_FROM` / `SMTP_USER` を Gmail アドレスに統一する

---

## 5. GitHub Actions Variables / Secrets 登録

### 5-1. 登録方法（推奨）

- [ ] `gh variable set ...` を使って Variables を登録
- [ ] `gh secret set ...` を使って Secrets を登録
- [ ] 登録コマンドを実行前に確認する（コピペ内容をレビュー）
- [ ] 補助スクリプトを使う場合は、まず preview-only（デフォルト）で確認する
- [ ] 変更を反映する時だけ `APPLY=1` を付ける

### 5-2. 登録確認

- [ ] `gh variable list` で Variables を確認
- [ ] `gh secret list` で Secrets 名を確認（値は表示されない）
- [ ] `TARGET_NAME` を Variable にするか Secret にするか最終確認

備考:
- このリポジトリでは `workflow` は `vars.*` / `secrets.*` の両方に対応済み（項目によって優先順あり）

---

## 6. 初回実行（GitHub Actions）

- [ ] `Actions` → `Daily Credit Check` → `Run workflow`
- [ ] `Authenticate to Google Cloud (WIF)` が成功
- [ ] `Run credit monitor` が実行される
- [ ] 失敗時のログを確認（WIF / Firestore / SMTP）

---

## 7. 初回実行後の確認（Firestore / メール）

- [ ] Firestore にコレクションが作成される
  - [ ] `runs`
  - [ ] `events`
  - [ ] `deliveries`
  - [ ] `snapshots`
- [ ] `runs.status` が期待どおり（`success` or `partial_failure`）
- [ ] Gmail 通知が届く（差分がある場合）
- [ ] `partial_failure` の場合、`deliveries` に失敗状態が残る

---

## 8. 運用確認（翌日以降）

- [ ] 失敗した `deliveries` が次回実行で再送される
- [ ] `runs/events/deliveries` の TTL が有効に機能している
- [ ] 意図しない重複通知が過剰に発生していない

---

## 9. 将来（Cloud Run へ移行する時）

- [ ] GitHub Variables/Secrets に入れた値を棚卸しする
- [ ] `Secrets` を Secret Manager に移す（`SMTP_PASS`, `LINE_NOTIFY_TOKEN` など）
- [ ] Cloud Run Job の `--set-env-vars` / `--set-secrets` をレビューして設定
- [ ] WIF は継続利用（GitHub→GCP 連携が必要な場合）

備考:
- 現在のコードは Cloud Run 移行を見据えた構成（Firestore + Outbox）になっている

---

## 10. 今日やらないこと（後回しでOK）

- [ ] Terraform 化（未実施なら後でやる）
- [ ] 監視ダッシュボード（BigQuery / Looker Studio）
- [ ] Cloud Run 移行
- [ ] Secret Manager への完全移行
