"""Animation refusals that happen after the probe and before the Kernel."""

import hashlib
import os
from pathlib import Path

from tests.host_permissions import deny_directory_listing
from tests.native_invocation import run
from tests.support import probe_only_aseprite


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preview(source: Path, destination: Path) -> dict:
    return {
        "source_sprite_file": str(source),
        "earlier_frame": 1,
        "later_frame": 2,
        "destination": {"path": str(destination), "if_exists": "replace"},
    }


def test_preview_reports_unverifiable_source_destination_identity(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    private.mkdir()
    source = private / "source.aseprite"
    source.write_bytes(b"source")
    destination = private / "preview.png"
    os.link(source, destination)
    original = _sha256(source)
    controlled = probe_only_aseprite(tmp_path)
    with deny_directory_listing(private):
        outcome = run(
            "animation preview",
            _preview(source, destination),
            aseprite=controlled,
        )

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "artifact_file_failed"
    assert (
        outcome.envelope["details"]["reason"]
        == "source_destination_identity_unverified"
    )
    assert _sha256(source) == original
    assert _sha256(destination) == original


def test_audit_reports_typed_coverage_limit_before_inspection(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    outcome = run(
        "animation audit",
        {
            "sprite_file": str(source),
            "from_frame": 1,
            "to_frame": 1,
            "required_cels": [
                {"layer": {"layer_path": [1]}, "frame_number": 1} for _ in range(1025)
            ],
        },
        aseprite=probe_only_aseprite(tmp_path),
    )

    assert outcome.returncode != 0
    assert outcome.envelope["code"] == "audit_limit_exceeded"
    assert outcome.envelope["details"] == {
        "kind": "operation_limit",
        "unit": "coverage_observations",
        "requested": 1025,
        "allowed_minimum": 0,
        "allowed_maximum": 1024,
    }
