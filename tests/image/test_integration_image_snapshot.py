"""Snapshot Artifact input refusals after the probe and before the Kernel."""

from pathlib import Path

import pytest

from tests.native_invocation import run
from tests.support import probe_only_aseprite


@pytest.mark.parametrize(
    "artifact_path", ["bad\u0000.json", "~spa-pr114-no-such-user/snapshot.json"]
)
def test_unusable_snapshot_artifact_path_returns_failure_without_commit(
    tmp_path: Path,
    artifact_path: str,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    source = work / "source.aseprite"
    source.write_bytes(b"source")
    destination = work / "existing.aseprite"
    destination.write_bytes(b"existing target")
    outcome = run(
        "image replace",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(destination),
            "in_place": False,
            "overwrite": True,
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "input": {"kind": "artifact", "path": artifact_path},
        },
        transport="stdin",
        aseprite=probe_only_aseprite(tmp_path),
    )
    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "artifact_file_failed", outcome.envelope
    assert outcome.envelope["details"]["reason"] == "input_file_unreadable"
    assert "Traceback" not in outcome.process.stderr
    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"existing target"
    assert set(work.iterdir()) == {source, destination}
