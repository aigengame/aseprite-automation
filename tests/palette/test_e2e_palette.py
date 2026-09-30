"""Public Palette operations against native Frame-based Palette Changes."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import inject_palette_change, process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _run(*command: str, **request: object) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def _fixture(source: Path, runtime, mode: str = "indexed") -> None:
    with tempfile.TemporaryDirectory(prefix="spa-palette-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"source={source}",
                "--script-param",
                f"mode={mode}",
                "--script",
                str(Path(__file__).parent / "fixtures" / "palette_changes.lua"),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)
    for frame, color in [(3, (40, 80, 220, 255)), (5, (220, 100, 30, 255))]:
        inject_palette_change(
            source,
            [(10, 20, 30, 255), color, (20, 200, 40, 128), (50, 60, 70, 0)],
            frame_number=frame,
        )


def test_list_and_get_distinguish_requested_frame_from_owning_change(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, runtime)
    original = source.read_bytes()
    code, listed = _run("palette", "list", sprite_file=str(source))
    assert code == 0, listed
    assert listed["frame_count"] == 5
    changes = listed["palette_changes"]
    assert [
        (change["palette_frame_number"], change["effective_frame_range"])
        for change in changes
    ] == [
        (1, {"from_frame": 1, "to_frame": 2}),
        (3, {"from_frame": 3, "to_frame": 4}),
        (5, {"from_frame": 5, "to_frame": 5}),
    ]
    assert [change["entries"][1]["color"]["red"] for change in changes] == [
        240,
        40,
        220,
    ]
    for requested, owner in [(5, 5), (1, 1), (2, 1), (3, 3), (4, 3)]:
        code, got = _run(
            "palette", "get", sprite_file=str(source), frame_number=requested
        )
        assert code == 0, got
        assert got["frame_number"] == requested
        assert got["palette"] == next(
            change for change in changes if change["palette_frame_number"] == owner
        )
    assert source.read_bytes() == original


def test_get_rejects_a_frame_outside_the_timeline(tmp_path: Path, runtime) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, runtime)
    code, result = _run("palette", "get", sprite_file=str(source), frame_number=6)
    assert code != 0 and result["code"] == "palette_frame_out_of_bounds", result
    assert result["details"]["frame_number"] == 6
    assert result["details"]["frame_count"] == 5
