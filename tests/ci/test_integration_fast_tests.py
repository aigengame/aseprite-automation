"""CI and Release run one fast tier, with Release actions from the workflow commit."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / ".github/actions/run-fast-tests/action.yml"


def _job(workflow: str, job: str) -> str:
    body = (ROOT / ".github/workflows" / workflow).read_text().split(f"\n  {job}:\n")[1]
    return re.split(r"\n  [a-z-]+:\n", body, maxsplit=1)[0]


def _steps(job: str) -> list[str]:
    return job.split("\n      - name: ")[1:]


def test_ci_and_release_share_one_fast_tier() -> None:
    # Release once ran the tier serially and exceeded its job time limit while CI
    # ran it in parallel. One action owns the arguments for both callers.
    for job in (_job("ci.yml", "fast-tests"), _job("release.yml", "quality")):
        [step] = [s for s in _steps(job) if s.startswith("Run fast tests\n")]
        assert "uses: ./.github/actions/run-fast-tests\n" in step
        assert "workers: ${{ vars.SPA_FAST_TEST_WORKERS }}\n" in step

    # A `-k` selection, such as the installed-wheel cases, is not the fast tier.
    tiers = [
        f"{owner.relative_to(ROOT)}: {line.strip()}"
        for owner in sorted((ROOT / ".github").rglob("*.yml"))
        for line in owner.read_text().splitlines()
        if 'pytest -m "not e2e"' in line and " -k " not in line
    ]
    assert tiers == [
        '.github/actions/run-fast-tests/action.yml: uv run --frozen --group test pytest -m "not e2e"'
    ]

    command = " ".join(
        line.strip() for line in ACTION.read_text().split("run: >-\n")[1].splitlines()
    )
    local = command.replace('"$SPA_FAST_TEST_WORKERS"', '"${SPA_FAST_TEST_WORKERS:-4}"')
    documented = re.sub(r"\s*\\\n\s*", " ", (ROOT / "docs/testing.md").read_text())
    assert f"\n{local}\n" in documented


def test_release_quality_tests_the_release_source_with_trusted_actions() -> None:
    # The draft can predate the workflow commit, so its tree can lack current actions.
    quality = _job("release.yml", "quality")
    assert (
        "\n    defaults:\n      run:\n        working-directory: release-source\n"
        in quality
    )
    trusted, source, *steps = _steps(quality)
    assert "ref: ${{ github.workflow_sha }}" in trusted
    assert "path:" not in trusted
    assert "ref: ${{ needs.prepare.outputs.release_sha }}" in source
    assert "path: release-source" in source

    local = [step for step in steps if "uses: ./" in step]
    assert all("uses: ./.github/actions/" in step for step in local)
    # Only the Lua tool installer runs without the project source.
    assert [
        step.split("\n", 1)[0]
        for step in local
        if "working-directory: release-source" not in step
    ] == ["Set up Lua quality tools"]
    assert "path: release-source/dist/" in quality
