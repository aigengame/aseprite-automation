"""Explicit Palette organization contracts and publication evidence."""

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalTargetFiles
from spa.authoring.color.palette import (
    PaletteRemapRequest,
    PaletteReorderRequest,
    PaletteResizeRequest,
    remap_palette,
)
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import operation_services, runtime_observation


def request(**changes: object) -> dict:
    return {
        "source_sprite_file": "source.aseprite",
        "target_sprite_file": "target.aseprite",
        "in_place": False,
        "overwrite": True,
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"mapping": []},
        {
            "mapping": [
                {"old_index": 0, "new_index": 0},
                {"old_index": 0, "new_index": 1},
            ]
        },
        {"mapping": [{"old_index": True, "new_index": 0}]},
        {"mapping": [{"old_index": 0, "new_index": -1}]},
        {
            "mapping": [{"old_index": 0, "new_index": 0}],
            "in_place": True,
            "overwrite": False,
        },
    ],
)
def test_remap_requires_unambiguous_index_mapping(changes: dict) -> None:
    with pytest.raises(ValidationError):
        PaletteRemapRequest.model_validate(request(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "palette-change"},
        {"scope": "sprite", "palette_frame_number": 1},
        {"mapping": [{"old_index": 0, "new_index": 1}]},
        {
            "mapping": [
                {"old_index": 0, "new_index": 0},
                {"old_index": 1, "new_index": 0},
            ]
        },
    ],
)
def test_reorder_requires_exact_scope_and_a_complete_permutation(changes: dict) -> None:
    payload = request(scope="sprite", mapping=[{"old_index": 0, "new_index": 0}])
    payload.update(changes)
    with pytest.raises(ValidationError):
        PaletteReorderRequest.model_validate(payload)


def test_resize_requires_an_explicit_color_list_even_when_it_is_empty() -> None:
    payload = request(palette_frame_number=1, size=2)
    with pytest.raises(ValidationError):
        PaletteResizeRequest.model_validate(payload)
    assert PaletteResizeRequest.model_validate({**payload, "entries": []}).entries == []


@pytest.mark.parametrize(
    "bad_evidence", ["not_reopened", "wrong_scope", "wrong_mapping"]
)
def test_remap_does_not_publish_unverified_evidence(
    tmp_path: Path, bad_evidence: str
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    intent = PaletteRemapRequest.model_validate(
        request(
            source_sprite_file=str(source),
            target_sprite_file=str(target),
            mapping=[{"old_index": 1, "new_index": 0}],
        )
    )
    evidence = {
        "frame_count": 1,
        "palette_changes": [
            {
                "palette_frame_number": 1,
                "effective_frame_range": {"from_frame": 1, "to_frame": 1},
                "entries": [
                    {
                        "index": 0,
                        "color": {"red": 0, "green": 0, "blue": 0, "alpha": 255},
                    }
                ],
            }
        ],
        "scope": "sprite",
        "mapping": [item.model_dump() for item in intent.mapping],
        "transparent_color_index_before": 1,
        "transparent_color_index_after": 0,
        "affected_images": [],
        "persisted_reopen_verified": True,
    }
    if bad_evidence == "not_reopened":
        evidence["persisted_reopen_verified"] = False
    elif bad_evidence == "wrong_scope":
        evidence["scope"] = "palette-change"
    else:
        evidence["mapping"] = []

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified")
        return KernelInvocationResult(
            payload=evidence,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = replace(
        operation_services(lambda _: runtime_observation("aseprite_palette_remap")),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(
        RuntimeIssue, match="Invalid persisted Palette mapping evidence"
    ):
        remap_palette(intent, services)
    assert source.read_bytes() == b"source" and target.read_bytes() == b"target"
    assert sorted(file.name for file in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]
