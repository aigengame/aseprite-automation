"""Sprite copy refusals that happen before the Kernel."""

import json
from pathlib import Path

from jsonschema import validate

from tests.support import probe_only_aseprite, spa


def _copy(source: Path, target: Path, aseprite: Path, *, overwrite: bool):
    return spa(
        "sprite",
        "copy",
        "--input-json",
        json.dumps(
            {
                "aseprite": str(aseprite),
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": overwrite,
            }
        ),
    )


def test_copy_requires_a_distinct_target(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"Source")
    run = _copy(source, source, probe_only_aseprite(tmp_path), overwrite=True)
    assert run.returncode == 2, run.stdout
    failure = json.loads(run.stdout)
    assert failure["code"] == "invalid_request"
    assert failure["details"]["errors"][0]["location"] == ["target_sprite_file"]
    assert failure["details"]["errors"][0]["code"] == "source_target_identity"
    assert source.read_bytes() == b"Source"
    assert not list(tmp_path.glob("*.staged.aseprite"))


def test_copy_reports_source_staging_failure_without_target_commit(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.aseprite"
    target = tmp_path / "copy.aseprite"
    run = _copy(missing, target, probe_only_aseprite(tmp_path), overwrite=False)
    assert run.returncode == 1, run.stdout
    failure = json.loads(run.stdout)
    validate(
        failure, json.loads(spa("sprite", "copy", "--schema").stdout)["failure_schema"]
    )
    assert failure["code"] == "sprite_copy_staging_failed"
    assert failure["details"] == {
        "kind": "sprite_copy_staging",
        "source_sprite_file": str(missing),
        "target_sprite_file": str(target),
    }
    assert not target.exists()
    assert not list(tmp_path.glob("*.staged.aseprite"))
