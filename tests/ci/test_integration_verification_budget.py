"""Exercise the CI budget through its command interface."""

import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_budget.py"


def run_budget(
    tmp_path: Path,
    *args: str,
    elapsed: float = 0,
    excluded: float = 0,
    budget: float = 20,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        env={
            **os.environ,
            "SPA_CI_STARTED_AT": str(time.monotonic() - elapsed),
            "SPA_CI_BUDGET_SECONDS": str(budget),
            "SPA_ASEPRITE_BUILD_SECONDS": str(excluded),
            "GITHUB_ENV": str(tmp_path / "environment"),
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_cold_build_time_is_excluded_from_verification(tmp_path: Path) -> None:
    result = run_budget(tmp_path, "check", elapsed=25, excluded=10)

    assert result.returncode == 0, result.stderr
    assert "Aseprite cold build excluded: 10.0s" in result.stdout
    assert "budget: 20.0s" in (tmp_path / "summary.md").read_text()


def test_cache_hit_does_not_exempt_spent_verification_time(tmp_path: Path) -> None:
    result = run_budget(tmp_path, "check", elapsed=25)

    assert result.returncode != 0
    assert "Aseprite cold build excluded: 0.0s" in result.stdout


def test_verification_command_failure_is_preserved(tmp_path: Path) -> None:
    result = run_budget(tmp_path, "run", sys.executable, "-c", "raise SystemExit(7)")

    assert result.returncode == 7


def test_verification_stops_at_remaining_budget(tmp_path: Path) -> None:
    result = run_budget(
        tmp_path,
        "run",
        sys.executable,
        "-c",
        "import time; time.sleep(1)",
        budget=0.2,
    )

    assert result.returncode == 124
    assert "Verification budget exhausted" in result.stderr


def test_only_an_executed_cold_build_records_excluded_time(tmp_path: Path) -> None:
    result = run_budget(
        tmp_path,
        "build",
        sys.executable,
        "-c",
        "import time; time.sleep(0.1); raise SystemExit(7)",
    )

    assert result.returncode == 7
    name, value = (tmp_path / "environment").read_text().strip().split("=", 1)
    assert name == "SPA_ASEPRITE_BUILD_SECONDS"
    assert 0.1 <= float(value) < 5


def test_exhausted_budget_does_not_start_more_work(tmp_path: Path) -> None:
    marker = tmp_path / "unexpected"
    result = run_budget(
        tmp_path,
        "run",
        sys.executable,
        "-c",
        f"from pathlib import Path; Path({str(marker)!r}).touch()",
        elapsed=25,
    )

    assert result.returncode == 124
    assert not marker.exists()


def test_timed_out_command_cannot_leave_a_child_running(tmp_path: Path) -> None:
    started = tmp_path / "started"
    marker = tmp_path / "unexpected"
    child = (
        "import time; from pathlib import Path; "
        f"Path({str(started)!r}).touch(); time.sleep(2); "
        f"Path({str(marker)!r}).touch()"
    )
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(5)"
    )
    result = run_budget(tmp_path, "run", sys.executable, "-c", parent, budget=1)

    assert result.returncode == 124
    assert started.exists()
    time.sleep(1.5)
    assert not marker.exists()
