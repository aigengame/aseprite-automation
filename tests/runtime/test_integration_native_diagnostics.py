"""Direct fixture diagnostics without crashing a real Aseprite process."""

import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture
from tests.support import exiting_aseprite


@pytest.mark.parametrize(
    ("status", "description"),
    [
        (13, "exit status 13"),
        pytest.param(
            -signal.SIGTERM,
            "SIGTERM",
            marks=pytest.mark.skipif(os.name == "nt", reason="POSIX signal fixture"),
        ),
    ],
)
def test_direct_fixture_retains_exit_status_and_both_output_streams(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    description: str,
) -> None:
    binary = exiting_aseprite(
        tmp_path, stdout="fixture stdout", stderr="fixture stderr", status=status
    )
    monkeypatch.setenv("SPA_TEST_ASEPRITE", str(binary))

    with pytest.raises(AssertionError) as failure:
        _run_fixture("controlled.lua")

    message = str(failure.value)
    assert f"exit status: {status}" in message
    assert description in message
    assert "fixture stdout" in message
    assert "fixture stderr" in message


def test_successful_direct_fixture_still_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    binary = exiting_aseprite(tmp_path, stdout="expected native result")
    monkeypatch.setenv("SPA_TEST_ASEPRITE", str(binary))
    _run_fixture("controlled.lua")


@pytest.mark.parametrize("phase", ["call", "setup", "expected"])
def test_probe_failure_evidence_reaches_pytest_reports(
    tmp_path: Path, phase: str
) -> None:
    # Windows has no signal termination, so its expected evidence is exit status 13.
    binary = exiting_aseprite(
        tmp_path,
        stdout="probe stdout",
        stderr="probe stderr",
        status=13 if os.name == "nt" else -signal.SIGTERM,
    )
    test_file = tmp_path / "test_probe.py"
    action = {
        "call": "    image_fixture(tmp_path)\n",
        "setup": "    pass\n",
        "expected": (
            "    with pytest.raises(RuntimeIssue):\n        image_fixture(tmp_path)\n"
        ),
    }[phase]
    setup = (
        "@pytest.fixture(autouse=True)\n"
        "def failed_setup(tmp_path):\n"
        "    image_fixture(tmp_path)\n"
        if phase == "setup"
        else ""
    )
    test_file.write_text(
        "import pytest\n"
        "from spa.contracts.ports import RuntimeIssue\n"
        "from tests.image.support import image_fixture\n"
        + setup
        + "def test_probe(tmp_path):\n"
        + action
        + "def test_after_probe():\n    pass\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "pytest",
            "-p",
            "tests.conftest",
            str(test_file),
            "-x",
            "-vv",
            "--tb=short",
            f"--basetemp={tmp_path / 'pytest-temp'}",
            f"--junitxml={report}",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "SPA_TEST_ASEPRITE": str(binary),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    transcript = result.stdout + result.stderr
    cases = ET.parse(report).findall(".//testcase")
    if phase == "expected":
        assert result.returncode == 0, transcript
        assert len(cases) == 2
        assert not any(case.find("failure") is not None for case in cases)
        return
    assert result.returncode == 1, transcript
    assert len(cases) == 1
    for evidence in (transcript, report.read_text(encoding="utf-8")):
        if os.name == "nt":
            assert '"exit_status": 13' in evidence
            assert "exited with status 13" in evidence
        else:
            assert '"exit_status": -15' in evidence
            assert "SIGTERM" in evidence
        assert "probe stdout" in evidence
        assert "probe stderr" in evidence
