"""Cross-suite pytest gates."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _require_real_aseprite_for_e2e(request: pytest.FixtureRequest) -> None:
    """Fail selected e2e tests when the configured Aseprite cannot run."""
    if request.node.get_closest_marker("e2e") is None:
        return

    configured = os.environ.get("SPA_TEST_ASEPRITE")
    if not configured:
        pytest.fail(
            "e2e tests need a real Aseprite executable; set SPA_TEST_ASEPRITE"
        )

    executable = Path(configured).expanduser()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        pytest.fail(
            "e2e tests need an executable SPA_TEST_ASEPRITE file; "
            f"configured path: {executable}"
        )
