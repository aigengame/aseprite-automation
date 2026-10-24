"""Lua fixture diagnostics without crashing a real Aseprite process."""

import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.native_invocation import run_lua
from tests.support import (
    controlled_runtime,
    exiting_aseprite,
    process_diagnostics,
    recording_aseprite,
)


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
def test_lua_fixture_failure_keeps_exit_status_and_both_output_streams(
    tmp_path: Path, status: int, description: str
) -> None:
    binary = exiting_aseprite(
        tmp_path, stdout="fixture stdout", stderr="fixture stderr", status=status
    )

    lua = run_lua(tmp_path / "controlled.lua", controlled_runtime(binary))

    assert lua.returncode == status
    message = process_diagnostics(lua)
    assert f"exit status: {status}" in message
    assert description in message
    assert "fixture stdout" in message
    assert "fixture stderr" in message


def test_lua_fixture_gets_each_parameter_as_one_script_param(tmp_path: Path) -> None:
    record = tmp_path / "arguments.txt"
    binary = recording_aseprite(tmp_path, record, "native result")
    script = tmp_path / "fixture.lua"
    response = tmp_path / "response.txt"
    out = tmp_path / "out file.aseprite"

    lua = run_lua(
        script,
        controlled_runtime(binary),
        response=response,
        out=out,
        uuids=True,
        nested=False,
        count=3,
    )

    assert lua.returncode == 0, process_diagnostics(lua)
    assert record.read_text(encoding="utf-8").splitlines() == [
        "\t".join(
            [
                "--batch",
                *("--script-param", f"response={response}"),
                *("--script-param", f"out={out}"),
                *("--script-param", "uuids=true"),
                *("--script-param", "nested=false"),
                *("--script-param", "count=3"),
                *("--script", str(script)),
            ]
        )
    ]
    assert response.read_text(encoding="utf-8") == "native result"


def _pytest(
    test_file: Path, report: Path, binary: Path, *options: str
) -> subprocess.CompletedProcess[str]:
    """Run test_file in a nested pytest with the project conftest and binary."""
    return subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "pytest",
            "-p",
            "tests.conftest",
            str(test_file),
            *options,
            f"--basetemp={test_file.parent / 'pytest-temp'}",
            f"--junitxml={report}",
        ],
        cwd=test_file.parent,
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
        "call": "    probe_runtime()\n",
        "setup": "    pass\n",
        "expected": (
            "    with pytest.raises(RuntimeIssue):\n        probe_runtime()\n"
        ),
    }[phase]
    setup = (
        "@pytest.fixture(autouse=True)\n"
        "def failed_setup(tmp_path):\n"
        "    probe_runtime()\n"
        if phase == "setup"
        else ""
    )
    test_file.write_text(
        "import os\n"
        "import pytest\n"
        "from spa.adapters.aseprite.aseprite import probe\n"
        "from spa.application.surface import PROBE_RESOURCES\n"
        "from spa.contracts.ports import RuntimeIssue, RuntimeRequest\n"
        "def probe_runtime():\n"
        "    aseprite = os.environ['SPA_TEST_ASEPRITE']\n"
        "    probe(RuntimeRequest(aseprite=aseprite), PROBE_RESOURCES)\n"
        + setup
        + "def test_probe(tmp_path):\n"
        + action
        + "def test_after_probe():\n    pass\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.xml"
    result = _pytest(test_file, report, binary, "-x", "-vv", "--tb=short")
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


def test_failed_session_probe_reports_its_diagnostics_once_per_test(
    tmp_path: Path,
) -> None:
    binary = exiting_aseprite(
        tmp_path, stdout="probe stdout", stderr="probe stderr", status=13
    )
    test_file = tmp_path / "test_session_probe.py"
    test_file.write_text(
        "def test_first(runtime):\n    pass\n\ndef test_second(runtime):\n    pass\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.xml"
    result = _pytest(test_file, report, binary)
    transcript = result.stdout + result.stderr
    assert result.returncode == 1, transcript
    errors = [case.find("error") for case in ET.parse(report).findall(".//testcase")]
    assert len(errors) == 2, transcript
    for error in errors:
        assert error is not None and error.text is not None, transcript
        assert error.text.count("Runtime diagnostics:") == 1, error.text
        assert "probe stderr" in error.text
