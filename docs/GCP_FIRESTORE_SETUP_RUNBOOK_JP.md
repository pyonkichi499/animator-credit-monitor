# GCP Firestore + WIF セットアップ手順書（Daily Credit Check 復旧用）

`STATE_BACKEND=firestore` で GitHub Actions の `Daily Credit Check` を本番運用するために、
GCP 側リソース（Firestore / Service Account / Workload Identity Federation）を新規構築する手順です。

- 実行者: GCP プロジェクトの Owner 相当権限を持つ人
- 実行環境: `gcloud` と `gh` が認証済みの端末
- 対象リポジトリ: `pyonkichi499/animator-credit-monitor`（default branch `develop`）
- 認証方式: Service Account JSON キーを使わない OIDC + WIF

> アプリ側（Firestore バックエンド）は実装済みのため、コード変更は不要です。本書は GCP と GitHub 設定のみを扱います。

---

## 0. 前提チェック

```bash
gcloud --version
gh auth status
gcloud auth list          # 目的の GCP アカウントでログイン済みか
gh repo view pyonkichi499/animator-credit-monitor --json nameWithOwner
```

- [ ] GCP プロジェクトがある（無ければ先に作成）
- [ ] 課金が有効（Firestore は課金アカウント必須）
- [ ] GitHub の当該リポジトリに対する admin 権限（Variables/Secrets 登録に必要）

---

## 1. 変数を決める

以降のコマンドは、この変数定義を同じシェルで実行している前提です。

```bash
# --- 必須: 自分の値へ変更 ---
export PROJECT_ID="your-project-id"
export FIRESTORE_LOCATION="asia-northeast1"   # 例: 東京。作成後は変更不可

# --- そのままで良い（このリポジトリ用）---
export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"
export SA_NAME="animator-credit-monitor"
export GITHUB_OWNER="pyonkichi499"
export GITHUB_REPO="animator-credit-monitor"
export GITHUB_REF="refs/heads/develop"        # main へ移行したら refs/heads/main

# --- 自動導出 ---
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
echo "PROJECT_NUMBER=$PROJECT_NUMBER / SA_EMAIL=$SA_EMAIL"
```

> `FIRESTORE_LOCATION` はロケーション（リージョン or マルチリージョン）で、**作成後に変更できません**。データの所在地・レイテンシ要件に合わせて選んでください。

---

## 2. API 有効化

```bash
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  firestore.googleapis.com \
  --project="$PROJECT_ID"
```

---

## 3. Firestore データベースを作成（Native mode）

デフォルトデータベース（`(default)`）を Native mode で作成します。

```bash
gcloud firestore databases create \
  --database="(default)" \
  --location="$FIRESTORE_LOCATION" \
  --type=firestore-native \
  --project="$PROJECT_ID"
```

確認:

```bash
gcloud firestore databases describe --database="(default)" --project="$PROJECT_ID" \
  --format='value(name,type,locationId)'
```

> 別データベース名を使う場合は、後述の GitHub Variable `FIRESTORE_DATABASE` に同じ名前を設定します。
> コレクションは初回実行時に自動作成されるため、手動作成は不要です。

---

## 4. Service Account 作成 + 権限付与

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Animator Credit Monitor (GitHub Actions)"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/datastore.user"
```

`roles/datastore.user` は Firestore Native mode の読み書きに対応します（管理操作は含まない最小権限）。

---

## 5. Workload Identity Pool / Provider を作成

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

> `attribute-condition` で「このリポジトリの、この ref からの実行」だけに限定しています。
> これにより他リポジトリや別ブランチから同じ Service Account を借用されるのを防ぎます。

Provider のリソース名を取得（GitHub Variable に登録する値）:

```bash
export WIF_PROVIDER="$(gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)')"
echo "$WIF_PROVIDER"
# 例: projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

---

## 6. Service Account の借用（impersonation）を許可

```bash
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_OWNER}/${GITHUB_REPO}"
```

---

## 7. GitHub Variables / Secrets を登録

ワークフローは非秘匿情報を `vars.*`、認証情報を `secrets.*` から参照します。

### Variables（必須）

```bash
gh variable set GCP_PROJECT_ID --body "$PROJECT_ID"
gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$WIF_PROVIDER"
gh variable set GCP_SERVICE_ACCOUNT --body "$SA_EMAIL"
gh variable set STATE_BACKEND --body "firestore"

# 監視対象（少なくとも一方。名前を伏せたい場合は TARGET_NAME を Secret に）
gh variable set TARGET_BANGUMI_ID --body "12345"

# まずは疎通確認のため console から。メールは動作確認後に切替
gh variable set NOTIFIER --body "console"
```

### Variables（任意 / 既定値で良ければ省略可）

```bash
gh variable set FIRESTORE_DATABASE --body "(default)"
gh variable set FIRESTORE_COLLECTION_PREFIX --body "prod"   # 例: prod_runs のように接頭辞
```

### メール通知に切り替える場合

Variables:

```bash
gh variable set NOTIFIER --body "email"
gh variable set SMTP_HOST --body "smtp.gmail.com"
gh variable set SMTP_PORT --body "587"
gh variable set SMTP_USE_TLS --body "true"
```

Secrets:

```bash
gh secret set SMTP_FROM
gh secret set SMTP_TO
gh secret set SMTP_USER
gh secret set SMTP_PASS
# 監視対象名を公開したくない場合
gh secret set TARGET_NAME
```

> Gmail を使う場合は 2 段階認証を有効化し、通常パスワードではなく App Password を `SMTP_PASS` に設定してください。

確認:

```bash
gh variable list
gh secret list
```

---

## 8. Firestore TTL を設定

`runs` / `events` / `deliveries` の `expiresAt` を TTL フィールドに設定します（`snapshots` は比較基準のため TTL なし）。

```bash
for group in runs events deliveries; do
  gcloud firestore fields ttls update expiresAt \
    --collection-group="$group" \
    --enable-ttl \
    --database="(default)" \
    --project="$PROJECT_ID"
done
```

> `FIRESTORE_COLLECTION_PREFIX` を設定した場合は、コレクショングループ名も接頭辞付き
> （例: `prod_runs`, `prod_events`, `prod_deliveries`）になります。上記の `group` を読み替えてください。
> TTL 設定は非同期で反映され、対象コレクションにドキュメントが存在してから有効になります。

---

## 9. 動作確認

1. GitHub → Actions → **Daily Credit Check** → **Run workflow**（手動実行）
2. 各ステップを確認:
   - [ ] `Validate workflow configuration` が成功
   - [ ] `Authenticate to Google Cloud (WIF)` が **skipped ではなく success**
   - [ ] `Run credit monitor` が設定エラーなく完了
3. Firestore（GCP Console or CLI）で作成を確認:
   - [ ] `runs` にレコードが作成される
   - [ ] 取得成功時に `snapshots` が作成/更新される
   - [ ] 差分検知時に `events` / `deliveries` が作成される
4. `NOTIFIER=console` で疎通できたら、必要に応じて **7. のメール設定** に切り替え、再度手動実行してメール受信を確認
5. 翌日の schedule 実行（00:00 UTC = 09:00 JST）が success になることを確認

---

## 10. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| WIF step が `skipped` | `GCP_WORKLOAD_IDENTITY_PROVIDER` / `GCP_SERVICE_ACCOUNT` が空、または `STATE_BACKEND` が firestore 以外 | Variables を再確認（7章） |
| `Permission denied` on Firestore | SA に `roles/datastore.user` 未付与 | 4章を再実行 |
| `unauthorized_client` / token 交換失敗 | `attribute-condition` の repository / ref 不一致 | 5章の条件と実行ブランチを確認 |
| `GCP_PROJECT_ID is required` | Variable 未登録 | `gh variable set GCP_PROJECT_ID` |
| `NOT_FOUND` database | Firestore 未作成 or DB 名不一致 | 3章、`FIRESTORE_DATABASE` を確認 |

---

## 11. クリーンアップ（不要になった場合のみ）

```bash
gcloud iam workload-identity-pools providers delete "$PROVIDER_ID" \
  --project="$PROJECT_ID" --location="global" --workload-identity-pool="$POOL_ID"
gcloud iam workload-identity-pools delete "$POOL_ID" \
  --project="$PROJECT_ID" --location="global"
gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID"
# Firestore データベースの削除はデータ消失を伴うため Console から慎重に実施
```

---

## 補足

- 本書は `docs/GCP_WIF_SETUP_FOR_GITHUB_ACTIONS.md`（WIF 個別手順）と
  `docs/SETUP_CHECKLIST_JP.md`（設定チェックリスト）を、Firestore 新規作成込みの
  end-to-end 手順として統合したものです。
- `main` ブランチ運用へ移行する場合は、`GITHUB_REF` と provider の `attribute-condition`
  を `refs/heads/main` に更新し、Provider を作り直すか条件を更新してください。
- IaC 化する場合は、本手順の `gcloud` コマンドを Terraform 等へ移植してください。
