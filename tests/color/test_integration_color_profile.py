"""Color Profile commands refuse a runtime before the Kernel runs."""

from collections.abc import Iterable
from pathlib import Path
from typing import get_args

from spa.contracts.public import RuntimeCapability
from tests.native_invocation import run
from tests.support import probe_only_aseprite


def _without(missing: str) -> Iterable[RuntimeCapability]:
    return [item for item in get_args(RuntimeCapability) if item != missing]


def test_standalone_convert_refuses_a_runtime_without_the_converter(
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"Source bytes")
    target.write_bytes(b"existing Target")
    binary = probe_only_aseprite(tmp_path, _without("aseprite_convert_color_profile"))
    outcome = run(
        "sprite convert-color-profile",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": True,
            "profile": {"kind": "srgb"},
        },
        aseprite=binary,
    )
    assert outcome.returncode == 1, outcome.process.stdout
    assert outcome.envelope["code"] == "runtime_incompatible", outcome.envelope
    assert outcome.envelope["details"]["missing_capabilities"] == [
        "aseprite_convert_color_profile"
    ]
    assert source.read_bytes() == b"Source bytes"
    assert target.read_bytes() == b"existing Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))
