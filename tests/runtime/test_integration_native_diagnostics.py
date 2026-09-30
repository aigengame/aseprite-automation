"""Direct fixture diagnostics without crashing a real Aseprite process."""

import os
import signal
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
