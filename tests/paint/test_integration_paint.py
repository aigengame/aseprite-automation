"""Public Paint request validation without a running Aseprite executable."""

from pathlib import Path

from tests.host_permissions import symlink_creation_permission
from tests.native_invocation import run


def test_apply_rejects_source_alias_to_a_target_symlink(tmp_path: Path) -> None:
    # The Target entry is itself a symlink, so Source and Target resolve to one file.
    # tests/contracts holds the form where the Target entry is a regular file.
    real = tmp_path / "real.aseprite"
    real.write_bytes(b"committed Sprite")
    target = tmp_path / "target.aseprite"
    source = tmp_path / "source.aseprite"
    with symlink_creation_permission():
        target.symlink_to(real)
        source.symlink_to(target)

    for in_place in (False, True):
        outcome = run(
            "paint apply",
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": in_place,
                "overwrite": True,
                "target": {"layer_path": [1], "frame_number": 1},
                "patch": {
                    "coordinate_space": "image-pixel",
                    "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                    "runs": [],
                },
                "clipping": "reject",
            },
            aseprite="/missing/aseprite",
        )

        # The runtime probe would refuse the missing executable with exit 1.
        assert outcome.returncode == 2, outcome.envelope
        assert outcome.envelope["code"] == "invalid_request"
        assert outcome.envelope["details"]["errors"] == [
            {
                "location": ["source_sprite_file"],
                "code": "source_target_identity",
                "message": "Source alias traverses the Target publication entry",
            }
        ]
        assert source.is_symlink() and target.is_symlink()
        assert real.read_bytes() == b"committed Sprite"
