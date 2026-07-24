#!/usr/bin/env bash

set -Eeuo pipefail

if ! SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"; then
    printf 'Error: Failed to resolve the script directory\n' >&2
    exit 1
fi
readonly SCRIPT_DIR
readonly UV_CACHE_DIR="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/uv-cache}"
export UV_CACHE_DIR

apply=false
assume_yes=false
created_commits=0
active_paths=()

readonly -a BUILD_FILES=(
    "pyproject.toml"
    "uv.lock"
    "requirements.lock"
    "requirements-dev.lock"
)
readonly -a CI_FILES=(
    ".github/workflows/ci.yml"
    ".github/workflows/daily-credit-check.yml"
)
readonly -a DOC_FILES=(
    "README.md"
    "CLAUDE.md"
    "CLAUDE-JP.md"
    "docs/AUTOMATION.md"
    "docs/AUTOMATION-JP.md"
    "docs/MAINTENANCE.md"
    "docs/MAINTENANCE-JP.md"
)
readonly -a HELPER_FILES=(
    "scripts/commit.sh"
    "scripts/README.md"
    "tests/test_commit_script.py"
)
readonly -a ALLOWED_FILES=(
    "${BUILD_FILES[@]}"
    "${CI_FILES[@]}"
    "${DOC_FILES[@]}"
    "${HELPER_FILES[@]}"
)

readonly BUILD_SUBJECT="build: プロジェクト管理と CI を uv に移行"
readonly BUILD_BODY_ONE="開発依存を dependency-groups に移し、Rye の lockfile を uv.lock に統合。"
readonly BUILD_BODY_TWO="CI と定期実行を setup-uv と --locked 同期へ切り替え、中間コミットでも実行環境の整合性を維持。"

readonly DOCS_SUBJECT="docs: uv ベースの開発手順に更新"
readonly DOCS_BODY_ONE="README、開発者向けガイド、日英の運用ドキュメントから Rye コマンドを置換。"
readonly DOCS_BODY_TWO="セットアップ、CLI 実行、テスト、cron と systemd の例を uv に統一。"

readonly HELPER_SUBJECT="chore: uv 移行用コミットスクリプトを追加"
readonly HELPER_BODY_ONE="uv 移行差分を build、docs、helper の3単位に分割してコミット。"
readonly HELPER_BODY_TWO="既定は検証のみとし、--apply 指定時だけ品質チェック後にパス単位でステージ。"

usage() {
    cat <<'EOF'
Usage:
  ./scripts/commit.sh [--apply] [--yes]

Validate the current Rye-to-uv migration and split it into three commits:

  1. build: dependency metadata, lockfiles, and GitHub Actions
  2. docs: development and operations documentation
  3. chore: this commit helper and its tests

The default mode is preview-only: it runs all checks and prints the commit plan
without staging or committing anything. Unrelated unstaged changes are left
untouched; an existing staged change aborts the script.

Options:
      --apply  Create the planned commits after validation
  -y, --yes    Skip the confirmation prompt (requires --apply)
  -h, --help   Show this help
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    "$@"
}

is_allowed_file() {
    local candidate="$1"
    local allowed

    for allowed in "${ALLOWED_FILES[@]}"; do
        if [[ "${candidate}" == "${allowed}" ]]; then
            return 0
        fi
    done
    return 1
}

group_has_changes() {
    local output

    if ! output="$(git status --porcelain=v1 --untracked-files=all -- "$@")"; then
        fail "Failed to inspect commit group"
    fi
    [[ -n "${output}" ]]
}

print_group() {
    local number="$1"
    local subject="$2"
    local body_one="$3"
    local body_two="$4"
    shift 4

    printf '%s. Commit message:\n' "${number}"
    printf '   %s\n\n' "${subject}"
    printf '   %s\n\n' "${body_one}"
    printf '   %s\n' "${body_two}"
    printf '   Files:\n'
    printf '   - %s\n' "$@"
}

restore_staged_group() {
    git restore --staged -- "$@" >/dev/null 2>&1 || true
}

cleanup_active_stage() {
    if ((${#active_paths[@]} > 0)); then
        restore_staged_group "${active_paths[@]}"
    fi
}

ensure_empty_index() {
    if ! git diff --cached --quiet; then
        fail "The index contains staged changes; refusing to mix commit groups"
    fi
}

capture_target_state() {
    local path

    git status --porcelain=v1 --untracked-files=all -- "${ALLOWED_FILES[@]}"
    for path in "${ALLOWED_FILES[@]}"; do
        if [[ -f "${path}" ]]; then
            printf 'file:%s:executable=%s:' "${path}" "$([[ -x "${path}" ]] && printf yes || printf no)"
            cksum "${path}"
        elif [[ -e "${path}" ]]; then
            printf 'other:%s\n' "${path}"
        else
            printf 'missing:%s\n' "${path}"
        fi
    done
}

commit_group() {
    local subject="$1"
    local body_one="$2"
    local body_two="$3"
    shift 3
    local -a paths=("$@")

    if ! group_has_changes "${paths[@]}"; then
        printf 'Skip: %s (no remaining changes)\n' "${subject}"
        return 0
    fi

    ensure_empty_index
    active_paths=("${paths[@]}")

    if ! run git add -- "${paths[@]}"; then
        fail "Failed to stage commit group: ${subject}"
    fi

    if git diff --cached --quiet; then
        fail "Commit group produced no staged changes: ${subject}"
    fi

    if ! run git diff --cached --check; then
        fail "Staged diff validation failed: ${subject}"
    fi

    printf '\nStaged changes for %s:\n' "${subject}"
    git diff --cached --stat
    printf '\nCommit message:\n%s\n\n%s\n\n%s\n\n' "${subject}" "${body_one}" "${body_two}"

    if ! run git commit --only -m "${subject}" -m "${body_one}" -m "${body_two}" -- "${paths[@]}"; then
        fail "Commit failed; this group was unstaged: ${subject}"
    fi

    ensure_empty_index
    active_paths=()
    # Assignment form avoids the set -e footgun where (( expr )) returns a
    # non-zero status whenever the arithmetic result is 0.
    created_commits=$((created_commits + 1))
}

trap cleanup_active_stage EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

while (($# > 0)); do
    case "$1" in
        --apply)
            apply=true
            shift
            ;;
        -y | --yes)
            assume_yes=true
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

if [[ "${assume_yes}" == true && "${apply}" == false ]]; then
    fail "--yes requires --apply"
fi

require_command git
require_command uv
require_command cksum

if ! REPO_ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
    fail "Not a git repository: ${SCRIPT_DIR}"
fi
readonly REPO_ROOT
cd "${REPO_ROOT}"

if ! BRANCH="$(git symbolic-ref --quiet --short HEAD)"; then
    fail "Detached HEAD is not supported"
fi
readonly BRANCH

if ! GIT_DIR="$(git rev-parse --absolute-git-dir)"; then
    fail "Failed to resolve the Git directory"
fi
readonly GIT_DIR
for marker in MERGE_HEAD REBASE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
    if [[ -e "${GIT_DIR}/${marker}" ]]; then
        fail "Finish the in-progress Git operation before running this script (${marker})"
    fi
done
if [[ -d "${GIT_DIR}/rebase-apply" || -d "${GIT_DIR}/rebase-merge" ]]; then
    fail "Finish the in-progress rebase before running this script"
fi

if [[ -n "$(git diff --name-only --diff-filter=U)" ]]; then
    fail "Resolve all merge conflicts before running this script"
fi

if ! git diff --cached --quiet; then
    fail "The index already contains staged changes; unstage them before running this script"
fi

changed_files=()
while IFS= read -r path; do
    [[ -n "${path}" ]] && changed_files+=("${path}")
done < <(
    {
        git diff --name-only
        git ls-files --others --exclude-standard
    } | LC_ALL=C sort -u
)

if ((${#changed_files[@]} == 0)); then
    fail "There are no changes to commit"
fi

unexpected_files=()
for path in "${changed_files[@]}"; do
    if ! is_allowed_file "${path}"; then
        unexpected_files+=("${path}")
    fi
done

target_files=()
for path in "${changed_files[@]}"; do
    if is_allowed_file "${path}"; then
        target_files+=("${path}")
    fi
done
if ((${#target_files[@]} == 0)); then
    fail "There are no uv migration changes to commit"
fi

[[ -f "uv.lock" ]] || fail "uv.lock is missing"
[[ ! -e "requirements.lock" ]] || fail "requirements.lock must be deleted"
[[ ! -e "requirements-dev.lock" ]] || fail "requirements-dev.lock must be deleted"
grep -q '^\[dependency-groups\]' pyproject.toml || fail "pyproject.toml has no [dependency-groups]"
grep -q '^\[tool\.uv\]' pyproject.toml || fail "pyproject.toml has no [tool.uv]"
if grep -q '^\[tool\.rye\]' pyproject.toml; then
    fail "pyproject.toml still contains [tool.rye]"
fi

printf 'Repository: %s\n' "${REPO_ROOT}"
printf 'Branch: %s\n\n' "${BRANCH}"
printf 'Validated migration files:\n'
printf '  - %s\n' "${target_files[@]}"
if ((${#unexpected_files[@]} > 0)); then
    printf '\nUnrelated unstaged files will be left untouched:\n'
    printf '  - %s\n' "${unexpected_files[@]}"
fi
printf '\nPlanned commits:\n'
print_group 1 \
    "${BUILD_SUBJECT}" \
    "${BUILD_BODY_ONE}" \
    "${BUILD_BODY_TWO}" \
    "${BUILD_FILES[@]}" \
    "${CI_FILES[@]}"
print_group 2 "${DOCS_SUBJECT}" "${DOCS_BODY_ONE}" "${DOCS_BODY_TWO}" "${DOC_FILES[@]}"
print_group 3 "${HELPER_SUBJECT}" "${HELPER_BODY_ONE}" "${HELPER_BODY_TWO}" "${HELPER_FILES[@]}"
printf '\n'

validated_target_state="$(capture_target_state)"

run uv sync --locked
run uv lock --check
run uv run --locked ruff check src/ tests/
run uv run --locked mypy src/
run uv run --locked pytest tests/ -q
run uv run --locked python -c \
    'from pathlib import Path; import yaml; [yaml.safe_load(path.read_text()) for path in Path(".github/workflows").glob("*.yml")]; print("workflow YAML: OK")'
run uv run --locked animator-credit-monitor --help
run git diff --check

if [[ "${apply}" == false ]]; then
    printf '\nPreview completed successfully; nothing was staged or committed.\n'
    printf 'Run ./scripts/commit.sh --apply when you are ready.\n'
    exit 0
fi

if [[ "${assume_yes}" == false ]]; then
    [[ -t 0 ]] || fail "Interactive confirmation is unavailable; rerun with --apply --yes"
    read -r -p "Create the three commits shown above on ${BRANCH}? [y/N] " reply
    [[ "${reply}" =~ ^[Yy]$ ]] || fail "Commit operation cancelled"
fi

if [[ "$(capture_target_state)" != "${validated_target_state}" ]]; then
    fail "Migration files changed during validation; review the changes and rerun the script"
fi

commit_group \
    "${BUILD_SUBJECT}" \
    "${BUILD_BODY_ONE}" \
    "${BUILD_BODY_TWO}" \
    "${BUILD_FILES[@]}" \
    "${CI_FILES[@]}"

commit_group \
    "${DOCS_SUBJECT}" \
    "${DOCS_BODY_ONE}" \
    "${DOCS_BODY_TWO}" \
    "${DOC_FILES[@]}"

commit_group \
    "${HELPER_SUBJECT}" \
    "${HELPER_BODY_ONE}" \
    "${HELPER_BODY_TWO}" \
    "${HELPER_FILES[@]}"

if group_has_changes "${ALLOWED_FILES[@]}"; then
    git status --short -- "${ALLOWED_FILES[@]}"
    fail "Commits were created, but uv migration changes remain"
fi

printf '\nCreated commits:\n'
git log -"${created_commits}" --format='%h %s'

remaining_changes="$(git status --porcelain=v1 --untracked-files=all)"
if [[ -n "${remaining_changes}" ]]; then
    printf '\nUnrelated changes left untouched:\n%s\n' "${remaining_changes}"
fi
