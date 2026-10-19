"""PNG Export refusals that happen before the runtime is selected or used."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.export.support import export_image_choices as _request
from tests.host_permissions import (
    deny_directory_listing,
    symlink_creation_permission,
)
from tests.native_invocation import run
from tests.support import spa

MISSING_ASEPRITE = "/missing/aseprite"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_export_alias_refusal_leaves_source_and_destination_unchanged(
    tmp_path: Path,
) -> None:
    # tests/contracts/test_unit_destination_rules.py holds the refusal itself
    # (source_symlink_aliases_destination). It does not check the bytes.
    destination = tmp_path / "image.png"
    destination.write_bytes(b"destination")
    source = tmp_path / "linked.aseprite"
    with symlink_creation_permission():
        source.symlink_to(destination)
    original = _sha256(source)

    outcome = run(
        "export image",
        _request(source, destination, if_exists="replace"),
        aseprite=MISSING_ASEPRITE,
    )

    assert outcome.returncode != 0
    assert outcome.envelope["details"]["reason"] == "source_destination_alias"
    assert source.is_symlink()
    assert _sha256(source) == original
    assert _sha256(destination) == original


def test_export_reports_unverifiable_source_destination_identity(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    private.mkdir()
    source = private / "source.aseprite"
    source.write_bytes(b"source")
    destination = private / "image.png"
    os.link(source, destination)
    original = _sha256(source)
    with deny_directory_listing(private):
        outcome = run(
            "export image",
            _request(source, destination, if_exists="replace"),
            aseprite=MISSING_ASEPRITE,
        )

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "artifact_file_failed"
    assert (
        outcome.envelope["details"]["reason"]
        == "source_destination_identity_unverified"
    )
    assert _sha256(source) == original
    assert _sha256(destination) == original


def test_export_refuses_existing_file_when_policy_is_fail(tmp_path: Path) -> None:
    # tests/contracts/test_unit_destination_rules.py holds the refusal itself
    # (destination_exists). It does not check the bytes or the staged files.
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destination = tmp_path / "image.png"
    destination.write_bytes(b"existing artifact")

    outcome = run(
        "export image", _request(source, destination), aseprite=MISSING_ASEPRITE
    )

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "artifact_file_failed"
    assert outcome.envelope["details"]["reason"] == "destination_exists"
    assert destination.read_bytes() == b"existing artifact"
    assert not list(tmp_path.glob("*.staged.png"))


def test_export_schema_refuses_unsupported_and_incomplete_choices(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    destination = tmp_path / "rejected.png"
    accepted = _request(source, destination)
    schema = json.loads(spa("export", "image", "--schema").stdout)
    validator = Draft202012Validator(schema["request_schema"])
    validator.validate({**accepted, "aseprite": MISSING_ASEPRITE})
    assert schema["execution_kind"] == "export"
    assert schema["side_effects"] == ["publishes one verified PNG Image Artifact"]

    rejected: list[tuple[str, object]] = [
        ("destination.path", str(tmp_path / "image.jpg")),
        ("destination.path", str(tmp_path / "image.PNG")),
        ("destination.path", str(tmp_path / "image.png") + "\n"),
        ("destination.path", str(tmp_path / "image\r.png")),
        ("destination.path", str(tmp_path / "image\x00.png")),
        ("source_sprite_file", str(source) + "\n"),
        ("source_sprite_file", str(tmp_path / "source\r.aseprite")),
        ("source_sprite_file", str(tmp_path / "source\x00.aseprite")),
        ("destination.if_exists", None),
        ("frame_number", 0),
        ("frame_number", None),
        ("export_image_area", None),
        ("layer_composition", None),
        ("composition_color_mode", None),
        ("composition_color_mode", "grayscale"),
        ("tag", "walk"),
        ("frame_range", [1, 2]),
        ("ignore_empty", True),
        (
            "export_image_area",
            {"kind": "bounds", "x": 0, "y": 0, "width": 1, "height": 1},
        ),
        ("selection", {"kind": "mask"}),
        ("layer_composition", "all"),
        ("include_layers", [[1]]),
        ("color_mode", "grayscale"),
        ("color_profile", "omit"),
        ("transparency", "background"),
        ("palette", {"kind": "quantize"}),
        ("outputs", [str(destination), str(tmp_path / "other.png")]),
        ("format", "png"),
    ]
    for location, value in rejected:
        request = deepcopy(accepted)
        parent, separator, field = location.partition(".")
        target = request[parent] if separator else request
        assert isinstance(target, dict)
        if value is None:
            target.pop(field if separator else parent)
        else:
            target[field if separator else parent] = value
        assert not validator.is_valid({**request, "aseprite": MISSING_ASEPRITE}), (
            location
        )
        outcome = run("export image", request, aseprite=MISSING_ASEPRITE)
        assert outcome.returncode == 2, (location, outcome.envelope)
        assert outcome.envelope["code"] == "invalid_request"
        assert not destination.exists()
