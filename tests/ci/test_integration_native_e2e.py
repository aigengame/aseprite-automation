"""Exercise native workflow shell steps with real Git and a controlled GitHub API."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/native-e2e.yml"


def run_step(
    name: str, repository: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    step = WORKFLOW.read_text().split(f"      - name: {name}\n", 1)[1]
    body = step.split("        run: |\n", 1)[1].split("\n      - ", 1)[0]
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", textwrap.dedent(body)],
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@pytest.fixture
def candidate(tmp_path: Path) -> tuple[Path, dict[str, str], dict]:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True, stderr=subprocess.PIPE
        ).strip()

    git("init", "--initial-branch=main")
    git("config", "user.name", "Native gate test")
    git("config", "user.email", "ci@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("commit", "--allow-empty", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("checkout", "-b", "feature")
    git("commit", "--allow-empty", "-m", "head")
    head = git("rev-parse", "HEAD")
    git("checkout", "main")
    git("merge", "--no-ff", "feature", "-m", "merge preview")
    merge = git("rev-parse", "HEAD")
    response = {
        "number": 125,
        "state": "open",
        "mergeable": True,
        "base": {"ref": "main", "sha": base},
        "head": {"sha": head},
        "merge_commit_sha": merge,
    }
    api = tmp_path / "pull.json"
    api.write_text(json.dumps(response))
    tools = tmp_path / "bin"
    tools.mkdir()
    gh = tools / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\nfrom pathlib import Path\n"
        "assert sys.argv[1:] == ['api', 'repos/example/spa/pulls/125']\n"
        "print(Path(os.environ['SPA_TEST_PR_RESPONSE']).read_text())\n"
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "SPA_TEST_PR_RESPONSE": str(api),
        "SPA_PR_NUMBER": "125",
        "SPA_NATIVE_TARGET": str(tmp_path / "spa-native-target.json"),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_REPOSITORY": "example/spa",
        "GITHUB_SHA": base,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
    }
    return tmp_path, env, response


def test_pr_gate_verifies_the_merge_instead_of_the_dispatch_sha(candidate) -> None:
    repository, env, response = candidate
    for name in (
        "Resolve the native test target",
        "Check the merge parents before testing",
        "Reject a changed PR after testing",
    ):
        result = run_step(name, repository, env)
        assert result.returncode == 0, result.stderr
    target = json.loads(Path(env["SPA_NATIVE_TARGET"]).read_text())
    assert target == {
        "kind": "pull_request",
        "number": 125,
        "base_ref": "main",
        "base": response["base"]["sha"],
        "head": response["head"]["sha"],
        "sha": response["merge_commit_sha"],
    }
    assert (
        Path(env["GITHUB_OUTPUT"]).read_text()
        == f"sha={response['merge_commit_sha']}\n"
    )
    summary = Path(env["GITHUB_STEP_SUMMARY"]).read_text()
    assert "PR target is unchanged after testing" in summary
    assert response["merge_commit_sha"] in summary


@pytest.mark.parametrize("mergeable", [False, None])
def test_unavailable_merge_preview_fails_before_checkout(candidate, mergeable) -> None:
    repository, env, response = candidate
    response["mergeable"] = mergeable
    Path(env["SPA_TEST_PR_RESPONSE"]).write_text(json.dumps(response))
    result = run_step("Resolve the native test target", repository, env)
    assert result.returncode != 0
    assert "PR has no current merge result" in result.stderr
    assert not Path(env["GITHUB_OUTPUT"]).exists()


@pytest.mark.parametrize("change", ["base", "head", "merge", "closed", "base_ref"])
def test_pr_changes_invalidate_native_evidence(candidate, change: str) -> None:
    repository, env, response = candidate
    assert run_step("Resolve the native test target", repository, env).returncode == 0
    if change in {"base", "head"}:
        response[change]["sha"] = "f" * 40
    elif change == "merge":
        response["merge_commit_sha"] = "f" * 40
    elif change == "base_ref":
        response["base"]["ref"] = "dev"
    else:
        response["state"] = "closed"
    Path(env["SPA_TEST_PR_RESPONSE"]).write_text(json.dumps(response))
    result = run_step("Reject a changed PR after testing", repository, env)
    assert result.returncode != 0
    assert "this run cannot admit merge" in result.stderr
    assert "unchanged after testing" not in Path(env["GITHUB_STEP_SUMMARY"]).read_text()


def test_stale_merge_parents_fail_before_native_setup(candidate) -> None:
    repository, env, response = candidate
    response["head"]["sha"] = "f" * 40
    Path(env["SPA_TEST_PR_RESPONSE"]).write_text(json.dumps(response))
    assert run_step("Resolve the native test target", repository, env).returncode == 0
    result = run_step("Check the merge parents before testing", repository, env)
    assert result.returncode != 0
    assert "Merge preview parents do not match" in result.stderr


@pytest.mark.parametrize("event", ["workflow_dispatch", "schedule"])
def test_main_verification_uses_the_exact_event_sha(candidate, event: str) -> None:
    repository, env, response = candidate
    env["SPA_PR_NUMBER"] = ""
    env["GITHUB_EVENT_NAME"] = event
    subprocess.run(
        ["git", "checkout", env["GITHUB_SHA"]],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    for name in (
        "Resolve the native test target",
        "Check the merge parents before testing",
        "Reject a changed PR after testing",
    ):
        result = run_step(name, repository, env)
        assert result.returncode == 0, result.stderr
    assert json.loads(Path(env["SPA_NATIVE_TARGET"]).read_text()) == {
        "kind": "branch",
        "ref": "refs/heads/main",
        "sha": response["base"]["sha"],
    }
    assert "PR target is unchanged" not in Path(env["GITHUB_STEP_SUMMARY"]).read_text()


def test_manual_dev_verification_checks_the_exact_integrated_event_sha(
    candidate,
) -> None:
    repository, env, response = candidate
    env.update(SPA_PR_NUMBER="", GITHUB_REF="refs/heads/dev")
    env["GITHUB_SHA"] = response["merge_commit_sha"]
    for name in (
        "Resolve the native test target",
        "Check the merge parents before testing",
        "Reject a changed PR after testing",
    ):
        result = run_step(name, repository, env)
        assert result.returncode == 0, result.stderr
    assert json.loads(Path(env["SPA_NATIVE_TARGET"]).read_text()) == {
        "kind": "branch",
        "ref": "refs/heads/dev",
        "sha": response["merge_commit_sha"],
    }
    assert "PR target is unchanged" not in Path(env["GITHUB_STEP_SUMMARY"]).read_text()


@pytest.mark.parametrize(
    ("event", "ref"),
    [("schedule", "refs/heads/dev"), ("workflow_dispatch", "refs/heads/feature")],
)
def test_branch_verification_rejects_unsupported_routes(candidate, event, ref) -> None:
    repository, env, _ = candidate
    env.update(SPA_PR_NUMBER="", GITHUB_EVENT_NAME=event, GITHUB_REF=ref)
    result = run_step("Resolve the native test target", repository, env)
    assert result.returncode != 0
    assert "requires main, or a manual dev dispatch" in result.stderr
    assert not Path(env["GITHUB_OUTPUT"]).exists()


def test_api_failure_cannot_validate_previous_success(candidate) -> None:
    repository, env, _ = candidate
    assert run_step("Resolve the native test target", repository, env).returncode == 0
    Path(env["SPA_TEST_PR_RESPONSE"]).write_text("not JSON")
    result = run_step("Reject a changed PR after testing", repository, env)
    assert result.returncode != 0
    assert "this run cannot admit merge" in result.stderr
