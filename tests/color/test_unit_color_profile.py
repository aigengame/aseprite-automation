"""Explicit profile branches and publication evidence are public contracts."""

from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from spa.adapters.files import LocalTargetFiles
from spa.authoring.color.profile import (
    AssignProfileRequest,
    ConvertProfileRequest,
    assign_profile,
)
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import operation_services, runtime_observation


def _request(**changes):
    return dict(
        source_sprite_file="source.aseprite",
        target_sprite_file="target.aseprite",
        in_place=False,
        overwrite=True,
        profile={"kind": "srgb"},
        **changes,
    )


@pytest.mark.parametrize(
    "profile",
    [
        {"kind": "SRGB"},
        {"kind": "icc"},
        {"kind": "icc", "icc_file": ""},
        {"kind": "srgb", "icc_file": "ignored.icc"},
        {"kind": "none", "name": "ignored"},
    ],
)
def test_profile_request_rejects_implicit_or_cross_branch_inputs(profile):
    request = _request()
    request["profile"] = profile
    with pytest.raises(ValidationError):
        AssignProfileRequest.model_validate(request)


def test_convert_cannot_target_none():
    request = _request()
    request["profile"] = {"kind": "none"}
    with pytest.raises(ValidationError):
        ConvertProfileRequest.model_validate(request)


@pytest.mark.parametrize(
    "corruption",
    [
        "not_reopened",
        "wrong_profile",
        "unequal_profile",
        "changed_image",
        "unknown_icc",
    ],
)
def test_invalid_native_receipts_do_not_publish(tmp_path: Path, corruption):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    request = _request()
    request.update(source_sprite_file=str(source), target_sprite_file=str(target))
    evidence = {
        "source_profile": {"kind": "srgb", "name": "sRGB"},
        "requested_profile": {"kind": "srgb", "name": "sRGB"},
        "effective_profile": {"kind": "srgb", "name": "sRGB"},
        "matches_requested_profile": True,
        "profile_changed": False,
        "icc_file": None,
        "persisted_reopen_verified": True,
        "images": [
            {
                "layer_path": [1],
                "frame_number": 1,
                "before_digest": "0" * 16,
                "after_digest": "0" * 16,
                "changed": False,
            }
        ],
        "palettes": [],
        "tilesets": [],
    }
    if corruption == "not_reopened":
        evidence["persisted_reopen_verified"] = False
    elif corruption == "wrong_profile":
        evidence["requested_profile"]["kind"] = "none"
    elif corruption == "unequal_profile":
        evidence["matches_requested_profile"] = False
    elif corruption == "changed_image":
        evidence["images"][0].update(after_digest="1" * 16, changed=True)
    else:
        evidence["icc_file"] = {
            "path": "ignored.icc",
            "byte_size": 1,
            "sha256": "0" * 64,
            "native_name": "sRGB",
            "matches_effective_profile": True,
        }

    def invoke(_runtime, _handler, payload, _timeout):
        Path(payload["staged_sprite_file"]).write_bytes(b"unverified")
        return KernelInvocationResult(
            payload=evidence,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    services = replace(
        operation_services(
            lambda _: runtime_observation("aseprite_assign_color_profile")
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    with pytest.raises(RuntimeIssue):
        assign_profile(AssignProfileRequest.model_validate(request), services)
    assert source.read_bytes() == b"source" and target.read_bytes() == b"target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))
