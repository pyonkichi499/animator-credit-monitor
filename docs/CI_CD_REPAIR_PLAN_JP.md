# CI/CD 修正計画

更新日: 2026-08-11

## 目的

CI と定期監視ワークフローを、次の順序で修正します。

1. 停止している `Daily Credit Check` を復旧する
2. CI の検証範囲を強化する
3. GitHub Actions の安全性を高める
4. `develop` 中心の運用を `main` 中心へ整理する

`Daily Credit Check` はデプロイ処理ではありませんが、本番相当の定期実行を担うため、本書では CD 相当の運用ワークフローとして扱います。

## 要約

| 優先度 | 変更 | 目的 |
|---|---|---|
| P0 | `Daily Credit Check` の設定、WIF、同時実行制御を修正 | 停止中の定期監視を復旧 |
| P1 | CIへPython matrix、lockfile、CLI、build検証を追加 | リリース可能性を継続検証 |
| P1 | GitHub Actionsをcommit SHAへ固定 | サプライチェーンリスクを低減 |
| P2 | default branchとWIF条件を`main`へ移行 | ブランチ運用を一本化 |

復旧、CI強化、Actions固定、ブランチ移行は、それぞれ別PRとして実施します。

## 現状

### CI

`.github/workflows/ci.yml` では、次の検証を実行しています。

- Ruff
- mypy
- pytest

現在の検証内容自体は正常に動作していますが、パッケージビルド、CLI起動、対応Pythonバージョン範囲の検証がありません。

### Daily Credit Check

`.github/workflows/daily-credit-check.yml` は、GitHub Variables が未設定の状態で空文字をアプリケーションへ渡しています。

確認されている主なエラー:

```text
Notifier type must be one of: console, email
SMTP_PORT must be an integer
GCP_PROJECT_ID is required when STATE_BACKEND=firestore
```

GCP関連設定はGitHub Secretsに登録されていますが、現在のworkflowは `vars.*` を参照しています。そのため、WIF認証がスキップされ、Firestoreへ接続できません。

## 優先順位別の修正方針

### P0: Daily Credit Checkの復旧

対象:

```text
.github/workflows/daily-credit-check.yml
GitHub Actions Variables / Secrets
```

#### 1. VariablesとSecretsの役割を統一する

非秘匿情報はVariables、認証情報や個人情報はSecretsに配置します。

#### GitHub Variables

```text
GCP_PROJECT_ID
GCP_WORKLOAD_IDENTITY_PROVIDER
GCP_SERVICE_ACCOUNT
STATE_BACKEND
FIRESTORE_DATABASE
FIRESTORE_COLLECTION_PREFIX
TARGET_BANGUMI_ID
NOTIFIER
NOTIFIERS
NOTIFY_RETRY_MAX_RETRIES
NOTIFY_RETRY_INITIAL_DELAY_SECONDS
SMTP_HOST
SMTP_PORT
SMTP_USE_TLS
EMAIL_SUBJECT_TEMPLATE
EMAIL_BODY_TEMPLATE
```

#### GitHub Secrets

```text
TARGET_NAME
SMTP_FROM
SMTP_TO
SMTP_USER
SMTP_PASS
```

既存のGCP関連Secretsは同名のVariablesへ再登録します。正常動作を確認した後、不要になったSecretsを削除します。

workflowを恒久的にVariablesとSecretsの両方へフォールバックさせるのではなく、保存場所を統一して設定ミスを検出しやすくします。

#### 2. workflow設定の事前検証を追加する

依存関係のインストールや監視処理より前に、必須設定を検証します。

検証対象:

- `TARGET_BANGUMI_ID` または `TARGET_NAME` のどちらかが設定されている
- `STATE_BACKEND` が `local` または `firestore`
- `NOTIFIER` または `NOTIFIERS` が設定されている
- Firestore使用時にWIF関連3項目が設定されている
- email使用時にSMTP必須項目が設定されている

想定する検証例:

```yaml
- name: Validate workflow configuration
  shell: bash
  env:
    TARGET_BANGUMI_ID: ${{ vars.TARGET_BANGUMI_ID }}
    TARGET_NAME: ${{ secrets.TARGET_NAME }}
    STATE_BACKEND: ${{ vars.STATE_BACKEND || 'firestore' }}
    GCP_PROJECT_ID: ${{ vars.GCP_PROJECT_ID }}
    GCP_WORKLOAD_IDENTITY_PROVIDER: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
    GCP_SERVICE_ACCOUNT: ${{ vars.GCP_SERVICE_ACCOUNT }}
    NOTIFIER: ${{ vars.NOTIFIER }}
    NOTIFIERS: ${{ vars.NOTIFIERS }}
  run: |
    set -euo pipefail

    [[ -n "${TARGET_BANGUMI_ID:-}" || -n "${TARGET_NAME:-}" ]] \
      || { echo "::error::TARGET_BANGUMI_ID or TARGET_NAME is required"; exit 1; }

    [[ -n "${NOTIFIER:-}" || -n "${NOTIFIERS:-}" ]] \
      || { echo "::error::NOTIFIER or NOTIFIERS is required"; exit 1; }

    if [[ "${STATE_BACKEND}" == "firestore" ]]; then
      [[ -n "${GCP_PROJECT_ID:-}" ]] \
        || { echo "::error::GCP_PROJECT_ID is required"; exit 1; }
      [[ -n "${GCP_WORKLOAD_IDENTITY_PROVIDER:-}" ]] \
        || { echo "::error::GCP_WORKLOAD_IDENTITY_PROVIDER is required"; exit 1; }
      [[ -n "${GCP_SERVICE_ACCOUNT:-}" ]] \
        || { echo "::error::GCP_SERVICE_ACCOUNT is required"; exit 1; }
    fi
```

現在のようにWIFが黙ってスキップされ、後続処理で複数の設定エラーになる状態を解消します。

email設定の検証では、`NOTIFIER` / `NOTIFIERS` に `email` が含まれる場合だけ、SMTP必須項目を同様に検査します。

#### 3. Firestore使用時はWIFをスキップさせない

現在の条件:

```yaml
if: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER != '' && vars.GCP_SERVICE_ACCOUNT != '' }}
```

修正後は、`STATE_BACKEND=firestore` の場合にWIF認証を必須とします。

```yaml
if: ${{ (vars.STATE_BACKEND || 'firestore') == 'firestore' }}
```

WIF設定が不足している場合は、認証ステップをスキップするのではなく、事前検証で明示的に失敗させます。

#### 4. 空文字でデフォルト値を上書きしない

workflowから未設定値を空文字で渡すと、アプリケーション側のデフォルト値が利用されません。workflow側でも安全なデフォルト値を指定します。

```yaml
STATE_BACKEND: ${{ vars.STATE_BACKEND || 'firestore' }}
FIRESTORE_DATABASE: ${{ vars.FIRESTORE_DATABASE || '(default)' }}
SMTP_PORT: ${{ vars.SMTP_PORT || '587' }}
SMTP_USE_TLS: ${{ vars.SMTP_USE_TLS || 'true' }}
NOTIFY_RETRY_MAX_RETRIES: ${{ vars.NOTIFY_RETRY_MAX_RETRIES || '2' }}
NOTIFY_RETRY_INITIAL_DELAY_SECONDS: ${{ vars.NOTIFY_RETRY_INITIAL_DELAY_SECONDS || '60' }}
EMAIL_SUBJECT_TEMPLATE: ${{ vars.EMAIL_SUBJECT_TEMPLATE || '{title}' }}
EMAIL_BODY_TEMPLATE: ${{ vars.EMAIL_BODY_TEMPLATE || '{message}' }}
```

`NOTIFIER`は意図しない通知先で運用を開始しないよう、デフォルト値には逃がさず必須設定として検証します。

#### 5. 同時実行を直列化する

schedule実行と手動実行が重なった場合の重複通知を抑えるため、workflowへ `concurrency` を追加します。

```yaml
concurrency:
  group: daily-credit-check-${{ github.ref }}
  cancel-in-progress: false
```

実行中の監視をキャンセルせず、後から開始されたrunを待機させます。

これはGitHub Actions内の重複実行に対する暫定対策です。Firestore側のtransaction、dedupe、delivery leaseは別途実装が必要です。

#### 6. local用キャッシュをFirestore実行時には使わない

`data/` の履歴キャッシュは `STATE_BACKEND=local` の場合だけ必要です。

```yaml
- name: Restore history cache
  if: ${{ (vars.STATE_BACKEND || 'firestore') == 'local' }}

- name: Ensure history directory exists
  if: ${{ always() && (vars.STATE_BACKEND || 'firestore') == 'local' }}

- name: Save history cache
  if: ${{ always() && (vars.STATE_BACKEND || 'firestore') == 'local' }}
```

Firestore運用時の不要なcache restore/saveを省き、状態管理先を明確にします。

#### 7. ジョブのタイムアウトを設定する

```yaml
jobs:
  check:
    timeout-minutes: 30
```

外部サービス障害や再送処理によって、ジョブが長時間runnerを占有することを防ぎます。

ただし、現在の再送処理は1件ごとに最大180秒待機する可能性があります。30分で十分かどうかは、再送処理の時間予算を実装する際に再検討します。

### P1: CIの強化

対象:

```text
.github/workflows/ci.yml
```

#### 1. Pythonバージョンのマトリクスを追加する

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.13"]
```

- Python 3.11: `requires-python` の最低サポートバージョン
- Python 3.13: 現在の開発環境で使用しているバージョン

`setup-uv` のPython設定もマトリクス値へ合わせます。

#### 2. 検証項目を追加する

追加予定:

```yaml
- name: Verify lockfile
  run: uv lock --check

- name: CLI smoke test
  run: uv run --locked animator-credit-monitor --help

- name: Build package
  run: uv build
```

CIの最終的な検証項目:

```text
uv lock --check
ruff
mypy
pytest
CLI smoke test
uv build
```

#### 3. 古いCI実行をキャンセルする

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

同じブランチへ連続pushした場合に、古いCIをキャンセルしてrunner消費を抑えます。

### P1: GitHub Actionsのサプライチェーン対策

現在、`astral-sh/setup-uv` はcommit SHAへ固定されています。一方、次のActionsはリリースタグ参照です。

```text
actions/checkout
google-github-actions/auth
actions/cache/restore
actions/cache/save
```

これらも検証済みのcommit SHAへ固定します。SHAには元のリリースバージョンをコメントとして残します。

```yaml
uses: actions/checkout@<COMMIT_SHA> # v4.x.x
```

具体的なSHAは実装時に各公式リポジトリの対象リリースを確認して決定します。

### P2: ブランチ運用の整理

現状:

```text
default branch: develop
main: developより遅れている
branch protection: 未設定
schedule: developで実行
WIF provider条件: refs/heads/develop
```

Daily Credit Checkの復旧とは別PRで、次の順序で変更します。

1. `develop` の変更を `main` へマージする
2. default branchを `main` へ変更する
3. WIF Providerの条件を `refs/heads/main` へ変更する
4. scheduleが `main` で成功することを確認する
5. `main` にbranch protectionを設定する
6. CI成功をマージ条件に設定する

復旧とブランチ移行を同時に行うと、障害発生時の原因切り分けが難しくなるため、変更単位を分離します。

## 実装単位

### PR 1: Daily Credit Check復旧

- VariablesとSecretsの役割統一
- workflow設定の事前検証
- Firestore時のWIF必須化
- デフォルト値の修正
- `concurrency` とtimeoutの追加
- localキャッシュの条件付き実行
- 関連ドキュメント更新

### PR 2: CI強化

- Python 3.11 / 3.13 matrix
- `uv lock --check`
- CLI smoke test
- `uv build`
- CI用 `concurrency`

### PR 3: Actions SHA固定

- 使用中Actionsのcommit SHA固定
- DependabotまたはRenovateによる更新方法の検討

### PR 4: mainブランチ運用への移行

- `develop` から `main` へのマージ
- default branch変更
- WIF条件変更
- branch protection設定

## 完了条件

### Daily Credit Check

- 手動実行でWIF認証が `success` になり、`skipped` にならない
- `Run credit monitor` が設定エラーなしで成功する
- Firestoreに `runs` と `snapshots` が作成される
- 差分検知時に `events` と `deliveries` が作成される
- 設定した通知先へ通知が届く
- 同じ状態で再実行して過剰な重複通知が発生しない
- 次回のschedule実行が成功する

### CI

- Python 3.11と3.13の両方でCIが成功する
- lockfile、lint、型、テスト、CLI、buildがすべて検証される
- PRで必須status checkとして利用できる

### ブランチ運用

- `main` がdefault branchになる
- WIFが `main` からの実行だけを許可する
- `main` への直接pushが制限される
- CI成功なしではマージできない

## 未確定事項

- 通知先を初回復旧時からemailにするか、最初はconsoleで疎通確認するか
- `TARGET_NAME` をSecretとして保持する必要があるか
- local backendをGitHub Actionsで今後も正式にサポートするか
- ジョブの適切なtimeout値
- Actionsを固定する具体的なcommit SHA
- `main` へ移行する時期
- Firestore再送クエリに必要な複合インデックスが実環境に存在するか
- Firestore TTLが `runs`、`events`、`deliveries` に設定済みか

## 今回の対象外

以下は重要ですが、CI/CD復旧とは別の実装課題として扱います。

- Firestoreのevent、delivery、snapshotのtransaction化
- `dedupeKey`を用いた実効的な重複防止
- deliveryのclaim／lease
- `maxAttempts`の強制とdead-letter
- Bangumi部分取得時のsnapshot更新防止
- AniListページネーション
- Firestore Emulatorを使用した統合テスト
