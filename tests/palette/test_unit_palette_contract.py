"""Palette contracts reject ambiguous edits and unverified publication evidence."""

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalTargetFiles
from spa.application.surface import info_result
from spa.authoring.color.palette import PaletteSetRequest, set_palette
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics, RuntimeRequest
from tests.support import operation_services, runtime_observation


def _request(**changes: object) -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": False,
        "palette_frame_number": 1,
        "entries": [
            {"index": 0, "color": {"red": 12, "green": 34, "blue": 56, "alpha": 77}}
        ],
        **changes,
    }


@pytest.mark.parametrize(
    "change",
    [
        {"entries": []},
        {"entries": [{"index": 0, "color": {"kind": "palette-index", "index": 1}}]},
        {
            "entries": [
                {"index": 0, "color": {"red": 1, "green": 2, "blue": 3, "alpha": 256}}
            ]
        },
        {"palette_frame_number": 0},
        {"palette_frame_number": True},
        {"palette_frame_number": 1.5},
        {"in_place": True, "overwrite": False},
    ],
)
def test_set_requires_explicit_valid_entry_edits(change: dict) -> None:
    with pytest.raises(ValidationError):
        PaletteSetRequest.model_validate(_request(**change))


def test_set_rejects_conflicting_entries() -> None:
    request = _request()
    request["entries"] *= 2
    with pytest.raises(ValidationError, match="only once"):
        PaletteSetRequest.model_validate(request)


def test_entry_edit_capability_is_required_only_for_set() -> None:
    services = operation_services(
        lambda _: runtime_observation("aseprite_sprite_inspection")
    )
    result = info_result(RuntimeRequest(), services)
    assert {"spa palette list", "spa palette get"} <= set(result.supported_capabilities)
    assert "spa palette set" not in result.supported_capabilities
    gap = next(
        gap for gap in result.capability_gaps if gap.capability == "spa palette set"
    )
    assert "aseprite_palette_entries" in gap.evidence


@pytest.mark.parametrize(
    "bad_evidence", ["wrong_entry", "missing_change", "wrong_range", "not_reopened"]
)
def test_set_does_not_publish_unverified_kernel_evidence(
    tmp_path: Path, bad_evidence: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"original source")
    target.write_bytes(b"original target")
    request = PaletteSetRequest.model_validate(
        _request(
            source_sprite_file=str(source),
            target_sprite_file=str(target),
            overwrite=True,
        )
    )
    change = {
        "palette_frame_number": 1,
        "effective_frame_range": {"from_frame": 1, "to_frame": 1},
        "entries": [entry.model_dump() for entry in request.entries],
    }
    evidence = {
        "frame_count": 1,
        "palette_changes": [change],
        "palette": change,
        "persisted_reopen_verified": True,
    }
    if bad_evidence == "wrong_entry":
        change["entries"][0]["color"]["alpha"] = 255
    elif bad_evidence == "missing_change":
        evidence["palette_changes"] = []
    elif bad_evidence == "wrong_range":
        change["effective_frame_range"]["to_frame"] = 2
    else:
        evidence["persisted_reopen_verified"] = False

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified output")
        return KernelInvocationResult(
            payload=evidence,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = replace(
        operation_services(lambda _: runtime_observation("aseprite_palette_entries")),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue, match="Invalid persisted Palette evidence"):
        set_palette(request, services)
    assert source.read_bytes() == b"original source"
    assert target.read_bytes() == b"original target"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]
