import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "commit.sh"

BUILD_FILES = [
    "pyproject.toml",
    "uv.lock",
    "requirements.lock",
    "requirements-dev.lock",
]
CI_FILES = [
    ".github/workflows/ci.yml",
    ".github/workflows/daily-credit-check.yml",
]
DOC_FILES = [
    "README.md",
    "CLAUDE.md",
    "CLAUDE-JP.md",
    "docs/AUTOMATION.md",
    "docs/AUTOMATION-JP.md",
    "docs/MAINTENANCE.md",
    "docs/MAINTENANCE-JP.md",
]
HELPER_FILES = [
    "scripts/commit.sh",
    "scripts/README.md",
    "tests/test_commit_script.py",
]
UNRELATED_FILE = "scripts/ask-fugu-usage-with-claude.sh"

EXPECTED_COMMITS = [
    (
        [
            "build: プロジェクト管理と CI を uv に移行",
            "開発依存を dependency-groups に移し、Rye の lockfile を uv.lock に統合。",
            "CI と定期実行を setup-uv と --locked 同期へ切り替え、中間コミットでも実行環境の整合性を維持。",
        ],
        BUILD_FILES + CI_FILES,
    ),
    (
        [
            "docs: uv ベースの開発手順に更新",
            "README、開発者向けガイド、日英の運用ドキュメントから Rye コマンドを置換。",
            "セットアップ、CLI 実行、テスト、cron と systemd の例を uv に統一。",
        ],
        DOC_FILES,
    ),
    (
        [
            "chore: uv 移行用コミットスクリプトを追加",
            "uv 移行差分を build、docs、helper の3単位に分割してコミット。",
            "既定は検証のみとし、--apply 指定時だけ品質チェック後にパス単位でステージ。",
        ],
        HELPER_FILES,
    ),
]

FAKE_GIT = r"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


state_path = Path(os.environ["FAKE_GIT_STATE"])


def load():
    return json.loads(state_path.read_text())


def save(state):
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def output_status(state, paths):
    statuses = state["statuses"]
    selected = paths or list(statuses)
    for path in selected:
        if path in statuses:
            print(f"{statuses[path]} {path}")


args = sys.argv[1:]
state = load()
state.setdefault("calls", []).append(args)
save(state)

if args[:1] == ["-C"]:
    args = args[2:]

if args == ["rev-parse", "--show-toplevel"]:
    print(state["repo_root"])
elif args == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
    if state.get("detached"):
        sys.exit(1)
    print(state["branch"])
elif args == ["rev-parse", "--absolute-git-dir"]:
    print(state["git_dir"])
elif args[:3] == ["diff", "--name-only", "--diff-filter=U"]:
    print("\n".join(state.get("conflicts", [])))
elif args[:3] == ["diff", "--cached", "--quiet"]:
    sys.exit(1 if state["staged"] else 0)
elif args[:3] == ["diff", "--cached", "--check"]:
    pass
elif args[:3] == ["diff", "--cached", "--stat"]:
    for path in state["staged"]:
        print(f" {path} | 1 +")
elif args == ["diff", "--name-only"]:
    for path, code in state["statuses"].items():
        if code != "??":
            print(path)
elif args == ["diff", "--check"]:
    pass
elif args[:3] == ["ls-files", "--others", "--exclude-standard"]:
    for path, code in state["statuses"].items():
        if code == "??":
            print(path)
elif args[:3] == ["status", "--porcelain=v1", "--untracked-files=all"]:
    paths = args[4:] if len(args) > 3 and args[3] == "--" else []
    output_status(state, paths)
elif args[:2] == ["status", "--short"]:
    paths = args[3:] if len(args) > 2 and args[2] == "--" else []
    output_status(state, paths)
elif args[:2] == ["add", "--"]:
    paths = args[2:]
    state["staged"] = [path for path in paths if path in state["statuses"]]
    save(state)
elif args[:3] == ["restore", "--staged", "--"]:
    paths = set(args[3:])
    state["staged"] = [path for path in state["staged"] if path not in paths]
    save(state)
elif args[:2] == ["commit", "--only"]:
    state["commit_attempts"] = state.get("commit_attempts", 0) + 1
    if state.get("fail_commit") == state["commit_attempts"]:
        save(state)
        print("simulated commit failure", file=sys.stderr)
        sys.exit(1)

    messages = []
    paths = []
    index = 2
    while index < len(args):
        if args[index] == "-m":
            messages.append(args[index + 1])
            index += 2
        elif args[index] == "--":
            paths = args[index + 1 :]
            break
        else:
            index += 1

    state["commits"].append({"messages": messages, "paths": paths})
    for path in paths:
        state["statuses"].pop(path, None)
    state["staged"] = [path for path in state["staged"] if path not in paths]
    save(state)
elif args and args[0].startswith("log"):
    for index, commit in enumerate(reversed(state["commits"]), start=1):
        print(f"fake{index:04d} {commit['messages'][0]}")
else:
    print(f"unsupported fake git invocation: {args!r}", file=sys.stderr)
    sys.exit(2)
"""

FAKE_UV = r"""#!/usr/bin/env bash
set -eu
if [[ -n "${FAKE_UV_MUTATE_PATH:-}" && ! -e "${FAKE_UV_MUTATE_MARKER:-}" ]]; then
  printf '\nchanged during validation\n' >> "$FAKE_UV_MUTATE_PATH"
  : > "$FAKE_UV_MUTATE_MARKER"
fi
case "$*" in
  *"pytest"*) printf '125 passed\n' ;;
  *"mypy"*) printf 'Success: no issues found\n' ;;
  *"ruff"*) printf 'All checks passed!\n' ;;
  *"workflow YAML"*) printf 'workflow YAML: OK\n' ;;
  *"animator-credit-monitor --help"*) printf 'Usage: animator-credit-monitor\n' ;;
  *) printf 'uv: OK\n' ;;
esac
"""


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _load_state(state_path: Path) -> dict:
    return json.loads(state_path.read_text())


@pytest.fixture
def fake_repository(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    repo = tmp_path / "repo"
    fake_bin = tmp_path / "bin"
    git_dir = tmp_path / "git-dir"
    state_path = tmp_path / "git-state.json"
    repo.mkdir()
    fake_bin.mkdir()
    git_dir.mkdir()

    _write(
        repo / "pyproject.toml",
        "[dependency-groups]\ndev = []\n\n[tool.uv]\nrequired-version = \"==0.11.24\"\n",
    )
    _write(repo / "uv.lock", "version = 1\n")

    for path in CI_FILES + DOC_FILES + HELPER_FILES:
        target = repo / path
        if path == "scripts/commit.sh":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPT_PATH, target)
            target.chmod(0o755)
        elif path == "tests/test_commit_script.py":
            _write(target, "# commit script tests\n")
        else:
            _write(target, f"{path}\n")
    _write(repo / UNRELATED_FILE, "# unrelated\n")

    fake_git = fake_bin / "git"
    fake_uv = fake_bin / "uv"
    _write(fake_git, FAKE_GIT)
    _write(fake_uv, FAKE_UV)
    fake_git.chmod(0o755)
    fake_uv.chmod(0o755)

    statuses = {
        **{path: " M" for path in BUILD_FILES + CI_FILES + DOC_FILES if not path.endswith(".lock")},
        "requirements.lock": " D",
        "requirements-dev.lock": " D",
        "uv.lock": "??",
        **{path: "??" for path in HELPER_FILES},
        UNRELATED_FILE: "??",
    }
    state = {
        "repo_root": str(repo),
        "git_dir": str(git_dir),
        "branch": "develop",
        "statuses": statuses,
        "staged": [],
        "commits": [],
        "calls": [],
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["FAKE_GIT_STATE"] = str(state_path)
    return repo, state_path, env


def _run_script(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(repo / "scripts" / "commit.sh"), *args],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        # Pin stdin to /dev/null so the interactive confirmation path is
        # deterministically non-TTY and can never block the test suite.
        stdin=subprocess.DEVNULL,
    )


def test_preview_does_not_run_mutating_git_commands(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository

    result = _run_script(repo, env)
    state = _load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert "Preview completed successfully" in result.stdout
    assert UNRELATED_FILE in result.stdout
    assert "build: プロジェクト管理と CI を uv に移行" in result.stdout
    assert "開発依存を dependency-groups に移し" in result.stdout
    assert state["commits"] == []
    assert state["staged"] == []
    assert not any(call and call[0] in {"add", "commit", "restore"} for call in state["calls"])


def test_apply_creates_three_multiline_commits_and_preserves_unrelated_changes(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository

    result = _run_script(repo, env, "--apply", "--yes")
    state = _load_state(state_path)

    assert result.returncode == 0, result.stderr
    assert len(state["commits"]) == 3
    for commit, (messages, paths) in zip(state["commits"], EXPECTED_COMMITS, strict=True):
        assert commit["messages"] == messages
        assert commit["paths"] == paths

    assert state["staged"] == []
    assert state["statuses"] == {UNRELATED_FILE: "??"}
    assert "Unrelated changes left untouched" in result.stdout


def test_failed_commit_is_unstaged_and_rerun_resumes_remaining_groups(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    state = _load_state(state_path)
    state["fail_commit"] = 2
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    failed = _run_script(repo, env, "--apply", "--yes")
    failed_state = _load_state(state_path)

    assert failed.returncode == 1
    assert len(failed_state["commits"]) == 1
    assert failed_state["staged"] == []

    failed_state.pop("fail_commit")
    failed_state["commit_attempts"] = 0
    state_path.write_text(json.dumps(failed_state, ensure_ascii=False, indent=2))

    resumed = _run_script(repo, env, "--apply", "--yes")
    resumed_state = _load_state(state_path)

    assert resumed.returncode == 0, resumed.stderr
    assert len(resumed_state["commits"]) == 3
    assert resumed_state["statuses"] == {UNRELATED_FILE: "??"}


def test_apply_rejects_an_existing_staged_change(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    state = _load_state(state_path)
    state["staged"] = [UNRELATED_FILE]
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    result = _run_script(repo, env, "--apply", "--yes")
    final_state = _load_state(state_path)

    assert result.returncode == 1
    assert "index already contains staged changes" in result.stderr
    assert final_state["commits"] == []


def test_apply_rejects_migration_files_changed_during_validation(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    env["FAKE_UV_MUTATE_PATH"] = str(repo / "pyproject.toml")
    env["FAKE_UV_MUTATE_MARKER"] = str(repo / ".fake-uv-mutated")

    result = _run_script(repo, env, "--apply", "--yes")
    final_state = _load_state(state_path)

    assert result.returncode == 1
    assert "changed during validation" in result.stderr
    assert final_state["commits"] == []
    assert final_state["staged"] == []


def test_apply_without_yes_refuses_to_commit_without_a_tty(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    # This is the core guarantee the user asked for: the script must never
    # create commits on its own. With --apply but no TTY and no --yes, it must
    # run the checks and then stop before staging or committing.
    repo, state_path, env = fake_repository

    result = _run_script(repo, env, "--apply")
    state = _load_state(state_path)

    assert result.returncode == 1
    assert "Interactive confirmation is unavailable" in result.stderr
    assert state["commits"] == []
    assert state["staged"] == []
    assert not any(call and call[0] in {"add", "commit", "restore"} for call in state["calls"])


def test_yes_without_apply_is_rejected(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository

    result = _run_script(repo, env, "--yes")
    state = _load_state(state_path)

    assert result.returncode == 1
    assert "--yes requires --apply" in result.stderr
    assert state["commits"] == []


def test_unknown_option_is_rejected(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository

    result = _run_script(repo, env, "--nope")

    assert result.returncode == 1
    assert "Unknown option: --nope" in result.stderr


def test_help_exits_zero_without_touching_git(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository

    result = _run_script(repo, env, "--help")
    state = _load_state(state_path)

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert state["calls"] == []


def test_apply_aborts_on_detached_head(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    state = _load_state(state_path)
    state["detached"] = True
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    result = _run_script(repo, env, "--apply", "--yes")
    final_state = _load_state(state_path)

    assert result.returncode == 1
    assert "Detached HEAD is not supported" in result.stderr
    assert final_state["commits"] == []


def test_apply_aborts_when_a_merge_is_in_progress(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    (Path(_load_state(state_path)["git_dir"]) / "MERGE_HEAD").write_text("x\n")

    result = _run_script(repo, env, "--apply", "--yes")
    final_state = _load_state(state_path)

    assert result.returncode == 1
    assert "in-progress Git operation" in result.stderr
    assert final_state["commits"] == []


def test_apply_aborts_on_unresolved_merge_conflict(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    state = _load_state(state_path)
    state["conflicts"] = ["pyproject.toml"]
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    result = _run_script(repo, env, "--apply", "--yes")
    final_state = _load_state(state_path)

    assert result.returncode == 1
    assert "Resolve all merge conflicts" in result.stderr
    assert final_state["commits"] == []


def test_reports_no_changes_when_only_unrelated_files_differ(
    fake_repository: tuple[Path, Path, dict[str, str]],
) -> None:
    repo, state_path, env = fake_repository
    state = _load_state(state_path)
    state["statuses"] = {UNRELATED_FILE: "??"}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    result = _run_script(repo, env)

    assert result.returncode == 1
    assert "no uv migration changes to commit" in result.stderr
