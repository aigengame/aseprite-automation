"""Run the hosted admission boundary without provisioning a private runner."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/native-e2e-shards.yml"
REPOSITORY = "aigengame/aseprite-automation"
SHA = "a" * 40


@pytest.fixture
def admission(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/.github/workflows/release.yml@refs/heads/main",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": SHA,
        "SPA_NATIVE_TARGET_JSON": json.dumps({"kind": "release", "sha": SHA}),
        "SPA_RELEASE_ID": "",
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
    }


def run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    body = WORKFLOW.read_text().split("          python3 - <<'PY'\n", 1)[1]
    script = textwrap.dedent(body.split("          PY\n", 1)[0])
    return subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_manual_release_admits_only_the_original_event_commit(admission) -> None:
    result = run(admission)
    assert result.returncode == 0, result.stderr
    outputs = dict(
        line.split("=", 1)
        for line in Path(admission["GITHUB_OUTPUT"]).read_text().splitlines()
    )
    assert json.loads(outputs["target"]) == {"kind": "release", "sha": SHA}

    Path(admission["GITHUB_OUTPUT"]).unlink()
    admission["SPA_NATIVE_TARGET_JSON"] = json.dumps(
        {"kind": "release", "sha": "b" * 40}
    )
    result = run(admission)
    assert result.returncode != 0
    assert "event commit" in result.stderr
    assert not Path(admission["GITHUB_OUTPUT"]).exists()


def test_automatic_release_resolves_the_draft_against_original_main_event(
    admission, tmp_path: Path
) -> None:
    admission.update(GITHUB_EVENT_NAME="push", SPA_RELEASE_ID="123")
    # The untagged draft can identify an earlier reviewed commit. Never resolve today's main.
    admission["GITHUB_SHA"] = "b" * 40
    gh = tmp_path / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "endpoint = sys.argv[2]\n"
        "if endpoint.endswith('/releases/123'):\n"
        "    print(json.dumps({'id': 123, 'target_commitish': os.environ['SPA_TEST_DRAFT_SHA']}))\n"
        f"elif endpoint.endswith('/compare/{SHA}...{'b' * 40}'):\n"
        "    print(json.dumps({'status': os.environ['SPA_TEST_ANCESTRY']}))\n"
        "else:\n"
        "    sys.exit('unexpected API request: ' + endpoint)\n"
    )
    gh.chmod(0o755)
    admission.update(
        PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        SPA_TEST_DRAFT_SHA=SHA,
        SPA_TEST_ANCESTRY="ahead",
    )
    result = run(admission)
    assert result.returncode == 0, result.stderr
    assert SHA in Path(admission["GITHUB_OUTPUT"]).read_text()

    for change in (
        {"SPA_TEST_DRAFT_SHA": "c" * 40},
        {"SPA_TEST_DRAFT_SHA": SHA, "SPA_TEST_ANCESTRY": "diverged"},
        {"SPA_RELEASE_ID": ""},
    ):
        Path(admission["GITHUB_OUTPUT"]).unlink(missing_ok=True)
        admission.update(change)
        result = run(admission)
        assert result.returncode != 0
        assert not Path(admission["GITHUB_OUTPUT"]).exists()


@pytest.mark.parametrize(
    "change",
    [
        {"GITHUB_REPOSITORY": "outsider/aseprite-automation"},
        {"GITHUB_EVENT_NAME": "pull_request"},
        {"GITHUB_EVENT_NAME": "pull_request_target"},
        {"GITHUB_EVENT_NAME": "schedule"},
        {"GITHUB_REF": "refs/heads/dev"},
        {
            "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/.github/workflows/other.yml@refs/heads/main"
        },
        {
            "GITHUB_WORKFLOW_REF": f"{REPOSITORY}/.github/workflows/release.yml@refs/heads/dev"
        },
        {"SPA_NATIVE_TARGET_JSON": json.dumps({"kind": "pull_request", "sha": SHA})},
        {"SPA_NATIVE_TARGET_JSON": json.dumps({"kind": "release", "sha": "main"})},
        {"SPA_NATIVE_TARGET_JSON": "{}"},
        {"SPA_NATIVE_TARGET_JSON": "not JSON"},
    ],
)
def test_untrusted_caller_or_target_cannot_emit_an_admission(admission, change) -> None:
    admission.update(change)
    result = run(admission)
    assert result.returncode != 0
    assert not Path(admission["GITHUB_OUTPUT"]).exists()


def test_api_failure_cannot_admit_a_release(admission, tmp_path: Path) -> None:
    gh = tmp_path / "gh"
    gh.write_text("#!/bin/sh\nexit 1\n")
    gh.chmod(0o755)
    admission.update(
        PATH=f"{tmp_path}{os.pathsep}{os.environ['PATH']}",
        GITHUB_EVENT_NAME="push",
        SPA_RELEASE_ID="123",
    )
    result = run(admission)
    assert result.returncode != 0
    assert not Path(admission["GITHUB_OUTPUT"]).exists()


def test_draft_access_is_confined_to_hosted_admission() -> None:
    # GitHub requires push access to read drafts. The caller sets the permission
    # ceiling; only hosted admission consumes it, without checking out project code.
    release = (ROOT / ".github/workflows/release.yml").read_text()
    caller = release.split("\n  shards:\n", 1)[1].split("\n  quality:\n", 1)[0]
    assert "\n    permissions:\n      contents: write\n" in caller

    workflow = WORKFLOW.read_text()
    assert "\npermissions:\n  contents: read\n" in workflow.split("\njobs:\n")[0]
    hosted = workflow.split("\n  admission:\n", 1)[1].split("\n  shard:\n", 1)[0]
    assert "\n    permissions:\n      contents: write\n" in hosted
    assert "runs-on: ubuntu-24.04" in hosted
    assert "uses:" not in hosted  # No checkout or action executes with this token.

    native = workflow.split("\n  shard:\n", 1)[1]
    assert "\n    permissions:\n      contents: read\n" in native
    assert "\npermissions:\n  contents: read\n" in release.split("\njobs:\n")[0]
    for job, following in (
        ("prepare", "shards"),
        ("quality", "verify"),
        ("verify", "publish-pypi"),
    ):
        body = release.split(f"\n  {job}:\n", 1)[1].split(f"\n  {following}:\n", 1)[0]
        # Test/build jobs retain the read-only default.
        assert "permissions:" not in body


def test_old_release_actions_cannot_replace_the_trusted_execution_tools() -> None:
    workflow = WORKFLOW.read_text()
    shard = workflow.split("  shard:\n", 1)[1]
    trusted = shard.split("      - name: Check out trusted execution tools\n", 1)[1]
    assert "ref: ${{ github.workflow_sha }}" in trusted.split("      - name:", 1)[0]
    target = shard.split("      - name: Check out the exact native target\n", 1)[1]
    checkout = target.split("      - name:", 1)[0]
    assert "path: native-target" in checkout
    assert "ref: ${{ fromJSON(needs.admission.outputs.target).sha }}" in checkout
    assert "uses: ./.github/actions/run-linux-aseprite-e2e" in target
    assert "source-directory: native-target" in target
    assert "./native-target/.github/actions/" not in shard
