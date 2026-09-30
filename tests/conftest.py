"""Cross-suite pytest gates and native failure evidence."""

import os
from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeIssue


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(call: pytest.CallInfo[None]):
    """Keep uncaught adapter evidence in the normal traceback and JUnit report."""
    if call.excinfo is not None and isinstance(call.excinfo.value, RuntimeIssue):
        issue = call.excinfo.value
        issue.add_note(
            "Runtime diagnostics:\n" + issue.diagnostics.model_dump_json(indent=2)
        )
    return (yield)


@pytest.fixture(autouse=True)
def _require_real_aseprite_for_e2e(request: pytest.FixtureRequest) -> None:
    """Fail selected e2e tests when the configured Aseprite cannot run."""
    if request.node.get_closest_marker("e2e") is None:
        return

    configured = os.environ.get("SPA_TEST_ASEPRITE")
    if not configured:
        pytest.fail("e2e tests need a real Aseprite executable; set SPA_TEST_ASEPRITE")

    executable = Path(configured).expanduser()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        pytest.fail(
            "e2e tests need an executable SPA_TEST_ASEPRITE file; "
            f"configured path: {executable}"
        )
