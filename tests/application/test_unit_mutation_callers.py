"""Standalone completion retains Source alias refusal before native work."""

from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import OPERATIONS
from spa.contracts.ports import OperationServices, RequestIssue

ADDRESS = {"layer": {"layer_path": [1]}, "frame_number": 1}
DESTINATION = {"layer": {"layer_path": [2]}, "frame_number": 2}


@pytest.mark.parametrize(
    ("operation", "options"),
    [
        ("cel set", {"target": ADDRESS, "opacity": 42}),
        ("cel copy", {"source": ADDRESS, "destination": DESTINATION}),
        ("cel link", {"source": ADDRESS, "destination": DESTINATION}),
        ("cel unlink", {"target": ADDRESS}),
        (
            "motion apply",
            {
                "layer": ADDRESS["layer"],
                "from_frame": 1,
                "to_frame": 1,
                "opacity": {
                    "interpolation": "step",
                    "rounding": "floor",
                    "keys": [{"frame_number": 1, "opacity": 42}],
                },
            },
        ),
    ],
)
@pytest.mark.parametrize("in_place", [False, True])
def test_source_alias_is_rejected_before_caller_probe_and_staging(
    tmp_path: Path, operation: str, options: dict, in_place: bool
) -> None:
    target, source = tmp_path / "target.aseprite", tmp_path / "alias.aseprite"
    target.write_bytes(b"existing Target")
    source.symlink_to(target)

    def unexpected(*_args):
        raise AssertionError("Source alias must fail before native work")

    descriptor = next(item for item in OPERATIONS if item.name == operation)
    with pytest.raises(RequestIssue) as rejected:
        request = descriptor.request_type.model_validate(
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": in_place,
                "overwrite": True,
                **options,
            }
        )
        descriptor.execute(
            request, OperationServices(unexpected, unexpected, LocalTargetFiles())
        )
    assert [issue.model_dump() for issue in rejected.value.issues] == [
        {
            "location": ["source_sprite_file"],
            "code": "source_target_identity",
            "message": "Source alias traverses the Target publication entry",
        }
    ]
    assert source.is_symlink()
    assert source.read_bytes() == target.read_bytes() == b"existing Target"
    assert set(tmp_path.iterdir()) == {source, target}
