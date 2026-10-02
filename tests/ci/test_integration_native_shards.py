"""Exercise the shared native entry point with small, real pytest sessions."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/native_e2e.py"


@pytest.fixture
def suite(tmp_path: Path) -> Path:
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    e2e: selected\n    slow: excluded\n"
    )
    for args in (
        ("init", "--initial-branch=main"),
        (
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "fixture",
        ),
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "test_cases.py").write_text(
        "import pytest\n"
        "@pytest.mark.e2e\n"
        "@pytest.mark.parametrize('value', range(6))\n"
        "def test_native(value):\n    assert value >= 0\n"
        "@pytest.mark.e2e\n@pytest.mark.slow\n"
        "def test_slow():\n    assert False\n"
        "def test_unit():\n    assert False\n"
    )
    return tmp_path


def run(suite: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("SPA_E2E_")}
    env.pop("PYTEST_ADDOPTS", None)
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=suite,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_shared_runner_covers_the_selected_suite_once(suite: Path) -> None:
    output = suite / "results"
    result = run(suite, "run", "--output-dir", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    reports = [
        json.loads(p.read_text()) for p in sorted(output.glob("shard-*/result.json"))
    ]
    assert len(reports) == 2
    assert [r["shard_index"] for r in reports] == [0, 1]
    assert all(r["workers"] == 2 for r in reports)
    expected = [f"test_cases.py::test_native[{i}]" for i in range(6)]
    assert [r["collection"] for r in reports] == [expected, expected]
    assert [sorted(o["nodeid"] for o in r["outcomes"]) for r in reports] == [
        [expected[0], expected[2], expected[4]],
        [expected[1], expected[3], expected[5]],
    ]
    assert "selected=6 passed=6 skipped=0" in result.stdout


def test_configuration_drives_matrix_and_nondefault_execution(suite: Path) -> None:
    matrix = run(suite, "matrix", "--shards", "3", "--workers", "1")
    assert matrix.returncode == 0, matrix.stderr
    assert json.loads(matrix.stdout) == {
        "include": [
            {"shard_index": 0, "shards": 3, "workers": 1},
            {"shard_index": 1, "shards": 3, "workers": 1},
            {"shard_index": 2, "shards": 3, "workers": 1},
        ]
    }
    output = suite / "results"
    result = run(
        suite, "run", "--shards", "3", "--workers", "1", "--output-dir", str(output)
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "selected=6 passed=6 skipped=0" in result.stdout
    assert len(list(output.glob("shard-*/result.json"))) == 3


def test_first_failure_stops_sibling_shards_but_preserves_its_report(
    suite: Path,
) -> None:
    (suite / "test_cases.py").write_text(
        "import time\nfrom pathlib import Path\nimport pytest\n"
        "pytestmark = pytest.mark.e2e\n"
        "def wait(name):\n"
        "    deadline = time.monotonic() + 10\n"
        "    while not Path(name).exists():\n"
        "        assert time.monotonic() < deadline\n"
        "        time.sleep(.01)\n"
        "def test_0_failure():\n"
        "    wait('sibling-running')\n    wait('primary-inflight')\n"
        "    Path('failure-ready').touch()\n"
        "    assert False, 'primary failure evidence'\n"
        "def test_1_sibling():\n"
        "    Path('sibling-running').touch()\n    time.sleep(60)\n"
        "    Path('sibling-completed').touch()\n"
        "def test_2_primary_inflight():\n"
        "    Path('primary-inflight').touch()\n    wait('failure-ready')\n"
        "    time.sleep(1)\n    Path('primary-completed').touch()\n"
        "def test_3_other():\n    pass\n"
    )
    output = suite / "results"
    result = run(suite, "run", "--output-dir", str(output))
    assert result.returncode != 0
    assert "primary failure evidence" in result.stdout
    assert (suite / "primary-completed").exists(), result.stdout + result.stderr
    assert not (suite / "sibling-completed").exists()
    report = json.loads((output / "shard-0/result.json").read_text())
    assert report["exit_code"] != 0
    assert sorted(o["outcome"] for o in report["outcomes"]) == ["failed", "passed"]


@pytest.mark.parametrize(
    "args",
    [
        ("--shards", "0"),
        ("--workers", "-1"),
        ("--shards", "bad"),
    ],
)
def test_invalid_configuration_is_rejected_before_execution(suite: Path, args) -> None:
    result = run(suite, "matrix", *args)
    assert result.returncode != 0
    assert not list(suite.glob("shard-*"))


@pytest.mark.parametrize("index", ["-1", "2"])
def test_invalid_shard_index_is_rejected(suite: Path, index: str) -> None:
    result = run(
        suite, "run", "--shard-index", index, "--output-dir", str(suite / "results")
    )
    assert result.returncode != 0
    assert "shard index" in result.stderr


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate-shard",
        "duplicate-case",
        "missing-case",
        "target",
        "collection",
        "cancelled",
        "missing-junit",
    ],
)
def test_aggregate_rejects_incomplete_or_mismatched_evidence(
    suite: Path, damage: str
) -> None:
    output = suite / "results"
    result = run(suite, "run", "--output-dir", str(output))
    assert result.returncode == 0, result.stdout + result.stderr
    path = output / "shard-1/result.json"
    report = json.loads(path.read_text())
    if damage == "missing":
        path.unlink()
    elif damage == "missing-junit":
        path.with_name("junit.xml").unlink()
    else:
        if damage == "duplicate-shard":
            report["shard_index"] = 0
        elif damage == "duplicate-case":
            report["outcomes"][0] = report["outcomes"][1]
        elif damage == "missing-case":
            report["outcomes"].pop()
        elif damage == "target":
            report["target"]["sha"] = "f" * 40
        elif damage == "collection":
            report["collection"][0] = "test_cases.py::test_native[-1]"
        elif damage == "cancelled":
            report["exit_code"] = 130
        path.write_text(json.dumps(report))
    result = run(suite, "verify", "--output-dir", str(output))
    assert result.returncode != 0, result.stdout
    assert "Native E2E failed" in result.stderr


def test_all_skipped_suite_and_reused_output_cannot_pass(suite: Path) -> None:
    path = suite / "test_cases.py"
    path.write_text(
        path.read_text().replace("assert value >= 0", "pytest.skip('platform')")
    )
    output = suite / "results"
    result = run(suite, "run", "--output-dir", str(output))
    assert result.returncode != 0
    assert "executed no tests" in result.stderr
    result = run(suite, "run", "--output-dir", str(output))
    assert result.returncode != 0
    assert "File exists" in result.stderr


def test_environment_configuration_has_one_default_and_explicit_overrides(
    suite: Path,
) -> None:
    env = {**os.environ, "SPA_E2E_SHARDS": "3", "SPA_E2E_WORKERS": "1"}
    result = subprocess.run(
        [sys.executable, str(RUNNER), "matrix", "--workers", "4"],
        cwd=suite,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    records = json.loads(result.stdout)["include"]
    assert len(records) == 3
    assert all(r["shards"] == 3 and r["workers"] == 4 for r in records)


def test_ambient_pytest_options_cannot_reduce_the_full_suite(suite: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER), "run", "--output-dir", str(suite / "results")],
        cwd=suite,
        env={**os.environ, "PYTEST_ADDOPTS": "-k [0]"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "selected=6 passed=6 skipped=0" in result.stdout
