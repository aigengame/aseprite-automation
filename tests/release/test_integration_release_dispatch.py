"""Exercise the release maintenance action with real Git and controlled remote APIs."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ACTION = (
    Path(__file__).resolve().parents[2]
    / ".github/actions/maintain-release-pr/action.yml"
)
BRANCH = "release-please--branches--main"


def dispatch_environment(
    tmp_path: Path, heads: list[str], remote: Path
) -> dict[str, str]:
    """Control GitHub responses, uv and waits; keep fetch, checkout and push real."""
    tools = tmp_path / "bin"
    tools.mkdir()
    responses = tmp_path / "heads.json"
    responses.write_text(json.dumps(heads))
    calls = tmp_path / "calls.jsonl"
    gh = tools / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, subprocess, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with Path(os.environ['SPA_TEST_GH_CALLS']).open('a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    source = Path(os.environ['SPA_TEST_GH_HEADS'])\n"
        "    heads = json.loads(source.read_text())\n"
        "    if heads[0] == 'remote':\n"
        "        subprocess.run(['git', '--git-dir', "
        "os.environ['SPA_TEST_GH_REMOTE'], 'rev-parse', "
        "'refs/heads/' + os.environ['SPA_RELEASE_BRANCH']], check=True)\n"
        "    else:\n"
        "        print(heads[0])\n"
        "    source.write_text(json.dumps(heads[1:] or heads))\n"
        "elif args[:2] != ['workflow', 'run']:\n"
        "    sys.exit(2)\n"
    )
    gh.chmod(0o755)
    sleep = tools / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    # Native uv/metadata behavior is outside this dispatch regression.
    uv = tools / "uv"
    uv.write_text(
        '#!/bin/sh\nif [ "$1" = lock ]; then\n'
        "  echo '# regenerated release lockfile' >> uv.lock\nfi\n"
    )
    uv.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "SPA_TEST_GH_HEADS": str(responses),
        "SPA_TEST_GH_CALLS": str(calls),
        "SPA_TEST_GH_REMOTE": str(remote),
        "GITHUB_REPOSITORY": "example/spa",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "SPA_RELEASE_PR_NUMBER": "111",
        "SPA_RELEASE_BRANCH": BRANCH,
    }


@pytest.mark.parametrize(
    ("heads", "expected_reads", "dispatches"),
    [
        pytest.param(["remote"], 1, True, id="head-already-matches"),
        pytest.param(["0" * 40, "remote"], 2, True, id="head-converges"),
        pytest.param(["0" * 40], 10, False, id="head-never-matches"),
    ],
)
def test_maintenance_dispatches_only_when_the_pushed_head_matches(
    tmp_path: Path, heads: list[str], expected_reads: int, dispatches: bool
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()

    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(repository), *arguments],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    git("init", "--initial-branch=main")
    git("config", "user.name", "Release test")
    git("config", "user.email", "release-test@example.invalid")
    git("config", "commit.gpgsign", "false")
    (repository / "uv.lock").write_text("# original lockfile\n")
    git("add", "uv.lock")
    git("commit", "-m", "chore: prepare current main")
    main_sha = git("rev-parse", "HEAD")
    git("checkout", "-b", BRANCH)
    (repository / "CHANGELOG.md").write_text("# Reviewed release change\n")
    git("add", "CHANGELOG.md")
    git("commit", "-m", "chore: prepare release change")
    before_maintenance_sha = git("rev-parse", "HEAD")
    remote = tmp_path / "origin.git"
    git("init", "--bare", str(remote))
    git("remote", "add", "origin", str(remote))
    git("push", "origin", BRANCH)
    git("checkout", "main")

    step = ACTION.read_text().split(
        "    - name: Refresh the generated lockfile and dispatch exact-head CI\n", 1
    )[1]
    run_body = step.split("      run: |\n", 1)[1].split("\n    - ", 1)[0]
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", textwrap.dedent(run_body)],
        cwd=repository,
        env=dispatch_environment(tmp_path, heads, remote),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    expected = git("rev-parse", "HEAD")
    assert git("branch", "--show-current") == BRANCH
    assert expected not in (main_sha, before_maintenance_sha)
    assert (
        git("--git-dir", str(remote), "rev-parse", f"refs/heads/{BRANCH}") == expected
    )
    assert git("diff", "--name-only", before_maintenance_sha, expected) == "uv.lock"
    calls = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert [call[:2] for call in calls] == [["pr", "view"]] * expected_reads + (
        [["workflow", "run"]] if dispatches else []
    )
    summary = (tmp_path / "summary.md").read_text()
    if dispatches:
        assert result.returncode == 0, result.stderr
        assert calls[-1] == [
            "workflow",
            "run",
            "ci.yml",
            "--repo",
            "example/spa",
            "--ref",
            BRANCH,
        ]
        assert f"Dispatched CI for exact head `{expected}`." in summary
    else:
        assert result.returncode != 0
        assert f"expected {expected}; observed {'0' * 40}" in result.stderr
        assert "CI was not dispatched" in result.stderr
        assert "Dispatched CI" not in summary
