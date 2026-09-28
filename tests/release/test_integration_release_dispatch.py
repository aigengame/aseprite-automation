"""Exercise release dispatch against controlled GitHub CLI responses."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dispatch_release_ci.sh"


def dispatch_environment(tmp_path: Path, heads: list[str]) -> dict[str, str]:
    """Control remote GitHub responses and waiting time, but keep Git real."""
    tools = tmp_path / "bin"
    tools.mkdir()
    responses = tmp_path / "heads.json"
    responses.write_text(json.dumps(heads))
    calls = tmp_path / "calls.jsonl"
    gh = tools / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with Path(os.environ['SPA_TEST_GH_CALLS']).open('a') as log:\n"
        "    log.write(json.dumps(args) + '\\n')\n"
        "if args[:2] == ['pr', 'view']:\n"
        "    source = Path(os.environ['SPA_TEST_GH_HEADS'])\n"
        "    heads = json.loads(source.read_text())\n"
        "    print(heads[0])\n"
        "    source.write_text(json.dumps(heads[1:] or heads))\n"
        "elif args[:2] != ['workflow', 'run']:\n"
        "    sys.exit(2)\n"
    )
    gh.chmod(0o755)
    sleep = tools / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "SPA_TEST_GH_HEADS": str(responses),
        "SPA_TEST_GH_CALLS": str(calls),
        "GITHUB_REPOSITORY": "example/spa",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "SPA_RELEASE_PR_NUMBER": "111",
        "SPA_RELEASE_BRANCH": "release-please--branches--main",
    }


def run_dispatch(
    tmp_path: Path, heads: list[str]
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env=dispatch_environment(tmp_path, heads),
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )
    calls = tmp_path / "calls.jsonl"
    return result, [json.loads(line) for line in calls.read_text().splitlines()]


def test_dispatch_waits_for_the_pushed_release_head(tmp_path: Path) -> None:
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SCRIPT.parents[1], text=True
    ).strip()

    result, calls = run_dispatch(tmp_path, ["0" * 40, expected])

    assert result.returncode == 0, result.stderr
    assert [call[:2] for call in calls] == [
        ["pr", "view"],
        ["pr", "view"],
        ["workflow", "run"],
    ]
    assert calls[-1] == [
        "workflow",
        "run",
        "ci.yml",
        "--repo",
        "example/spa",
        "--ref",
        "release-please--branches--main",
    ]
    assert expected in (tmp_path / "summary.md").read_text()


def test_dispatch_refuses_a_head_that_never_matches(tmp_path: Path) -> None:
    observed = "0" * 40

    result, calls = run_dispatch(tmp_path, [observed])

    assert result.returncode != 0
    assert 1 < len(calls) <= 10
    assert all(call[:2] == ["pr", "view"] for call in calls)
    assert observed in result.stderr
    assert "expected" in result.stderr
    assert "CI was not dispatched" in result.stderr
    assert not (tmp_path / "summary.md").exists()


def test_dispatch_needs_no_wait_when_head_already_matches(tmp_path: Path) -> None:
    expected = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=SCRIPT.parents[1], text=True
    ).strip()

    result, calls = run_dispatch(tmp_path, [expected])

    assert result.returncode == 0, result.stderr
    assert [call[:2] for call in calls] == [["pr", "view"], ["workflow", "run"]]


def test_maintenance_dispatches_a_stale_release_branch_without_helper(
    tmp_path: Path,
) -> None:
    """Run the action's shell with a real checkout that removes the new helper."""
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
    (repository / "uv.lock").write_text("# unchanged release lockfile\n")
    git("add", "uv.lock")
    git("commit", "-m", "chore: prepare release branch")
    release_sha = git("rev-parse", "HEAD")
    branch = "release-please--branches--main"
    git("branch", branch)
    remote = tmp_path / "origin.git"
    git("init", "--bare", str(remote))
    git("remote", "add", "origin", str(remote))
    git("push", "origin", branch)

    helper = repository / "scripts" / SCRIPT.name
    helper.parent.mkdir()
    helper.write_bytes(SCRIPT.read_bytes())
    git("add", "scripts")
    git("commit", "-m", "fix: add release dispatch helper on main")
    assert git("rev-parse", "HEAD") != release_sha

    environment = dispatch_environment(tmp_path, [release_sha])
    # uv's installation/lock/metadata work is outside this checkout regression.
    uv = tmp_path / "bin" / "uv"
    uv.write_text("#!/bin/sh\nexit 0\n")
    uv.chmod(0o755)
    runtime_temp = tmp_path / "runner-temp"
    runtime_temp.mkdir()
    environment["RUNNER_TEMP"] = str(runtime_temp)

    action = SCRIPT.parents[1] / ".github/actions/maintain-release-pr/action.yml"
    step = action.read_text().split(
        "    - name: Refresh the generated lockfile and dispatch exact-head CI\n", 1
    )[1]
    run_body = step.split("      run: |\n", 1)[1].split("\n    - ", 1)[0]
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", textwrap.dedent(run_body)],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert git("rev-parse", "HEAD") == release_sha
    assert not helper.exists()
    calls = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert [call[:2] for call in calls] == [["pr", "view"], ["workflow", "run"]]
    assert calls[-1] == [
        "workflow",
        "run",
        "ci.yml",
        "--repo",
        "example/spa",
        "--ref",
        branch,
    ]
    assert release_sha in (tmp_path / "summary.md").read_text()
