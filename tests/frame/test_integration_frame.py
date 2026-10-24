"""Frame field bounds refuse the request before any runtime or file mutation."""

from pathlib import Path
from typing import Any

import pytest

from tests.native_invocation import run


@pytest.mark.parametrize(
    ("command", "fields", "location"),
    [
        ("frame add", {"frame_number": 0, "duration_ms": 100}, ["frame_number"]),
        ("frame add", {"frame_number": 2, "duration_ms": 0}, ["duration_ms"]),
        ("frame add", {"frame_number": 2, "duration_ms": 65536}, ["duration_ms"]),
        ("frame set", {"frame_number": 1, "duration_ms": 0}, ["duration_ms"]),
    ],
)
def test_out_of_bounds_field_never_publishes_target(
    tmp_path: Path, command: str, fields: dict[str, Any], location: list[str]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    source.write_bytes(b"Source must remain unchanged")
    outcome = run(
        command,
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            **fields,
        },
        aseprite="/missing/aseprite",
    )
    assert outcome.returncode == 2, outcome.process.stdout
    assert outcome.envelope["code"] == "invalid_request"
    assert [error["location"] for error in outcome.envelope["details"]["errors"]] == [
        location
    ]
    assert not target.exists()
    assert source.read_bytes() == b"Source must remain unchanged"
