"""Direct fixture diagnostics without crashing a real Aseprite process."""

import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.frame.test_e2e_frame import _run_fixture
from tests.support import fake_aseprite


@pytest.mark.parametrize(
    ("termination", "status", "description"),
    [
        ("exit 13", 13, "exit status 13"),
        pytest.param(
            "kill -TERM $$",
            -signal.SIGTERM,
            "SIGTERM",
            marks=pytest.mark.skipif(os.name == "nt", reason="POSIX signal fixture"),
        ),
    ],
)
def test_direct_fixture_retains_exit_status_and_both_output_streams(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    termination: str,
    status: int,
    description: str,
) -> None:
    binary = fake_aseprite(
        tmp_path, f"echo 'fixture stdout'\necho 'fixture stderr' >&2\n{termination}\n"
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
    binary = fake_aseprite(tmp_path, "echo 'expected native result'\nexit 0\n")
    monkeypatch.setenv("SPA_TEST_ASEPRITE", str(binary))
    _run_fixture("controlled.lua")


@pytest.mark.parametrize("phase", ["call", "setup", "expected"])
def test_probe_failure_evidence_reaches_pytest_reports(
    tmp_path: Path, phase: str
) -> None:
    binary = fake_aseprite(
        tmp_path, "echo 'probe stdout'\necho 'probe stderr' >&2\nkill -TERM $$\n"
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
        + "def test_after_probe():\n    pass\n"
    )
    report = tmp_path / "report.xml"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.conftest",
            str(test_file),
            "-x",
            "-vv",
            "--tb=short",
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
    for evidence in (transcript, report.read_text()):
        assert '"exit_status": -15' in evidence
        assert "SIGTERM" in evidence
        assert "probe stdout" in evidence
        assert "probe stderr" in evidence
