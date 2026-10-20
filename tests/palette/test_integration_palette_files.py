"""Palette file decoder refusals through the public CLI, before the Kernel."""

import json
from pathlib import Path

from jsonschema import validate

from tests.native_invocation import run
from tests.palette.support import oversized_palette_png
from tests.support import probe_only_aseprite, spa


def _import(tmp_path: Path, palette_file: dict, palette_frame_number: int):
    """Import into placeholder sprites with an Aseprite that refuses the Kernel."""
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"placeholder source")
    target.write_bytes(b"keep target")
    aseprite = probe_only_aseprite(tmp_path)
    files_before = set(tmp_path.iterdir())
    outcome = run(
        "palette import",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "palette_frame_number": palette_frame_number,
            "palette_file": palette_file,
        },
        aseprite=aseprite,
    )
    assert source.read_bytes() == b"placeholder source"
    assert target.read_bytes() == b"keep target"
    assert set(tmp_path.iterdir()) == files_before
    return outcome


def test_import_png_decoder_refusal_uses_failure_envelope(tmp_path: Path) -> None:
    colors = tmp_path / "bad.png"
    colors.write_bytes(oversized_palette_png())

    outcome = _import(tmp_path, {"format": "png", "path": str(colors)}, 1)

    result = outcome.envelope
    assert outcome.returncode == 2 and result["code"] == "palette_file_failed", result
    assert result["details"]["reason"] == "invalid"
    assert "decompression bomb" in result["details"]["message"]
    schema_run = spa("palette", "import", "--schema")
    assert schema_run.returncode == 0, schema_run.stderr
    validate(result, json.loads(schema_run.stdout)["failure_schema"])


def test_import_gpl_decoder_refuses_a_component_outside_the_byte_range(
    tmp_path: Path,
) -> None:
    colors = tmp_path / "colors.gpl"
    colors.write_text("GIMP Palette\n256 0 0 wrong\n")

    outcome = _import(tmp_path, {"format": "gpl", "path": str(colors)}, 3)

    result = outcome.envelope
    assert outcome.returncode != 0 and result["code"] == "palette_file_failed", result
