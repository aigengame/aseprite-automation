"""Malformed Kernel observations and failed staging must not publish a Slice edit."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.authoring.document.slice import SliceSetRequest, set_slice
from spa.contracts.ports import KernelInvocationResult, RuntimeIssue
from spa.contracts.public import Diagnostics
from tests.support import operation_services, runtime_observation


def response():
    item = {
        "slice_index": 1,
        "name": "before",
        "data": "",
        "color": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
        "keys": [
            {
                "frame_number": 1,
                "bounds": {"x": -1, "y": 0, "width": 3, "height": 2},
                "center": None,
                "pivot": None,
                "effective_frame_range": {"from_frame": 1, "to_frame": 2},
            }
        ],
    }
    return {
        "operation": "set",
        "persisted_reopen_verified": True,
        "selected_before_index": 1,
        "before": {"frame_count": 2, "slices": [item]},
        "snapshot": {"frame_count": 2, "slices": [{**deepcopy(item), "name": "after"}]},
    }


def staging(tmp_path, evidence, *, crash=False, redirect=False):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    source.write_bytes(b"original")
    target.write_bytes(b"existing")
    stages = []

    def invoke(_observation, _handler, payload, _timeout):
        staged = Path(payload["staged_sprite_file"])
        staged.write_bytes(b"native output")
        stages.append(staged)
        if crash:
            raise RuntimeError("interrupted")
        if redirect:
            source.unlink()
            source.symlink_to(target)
        return KernelInvocationResult(evidence, "/response.json", Diagnostics())

    services = replace(
        operation_services(
            lambda _: runtime_observation(
                "aseprite_sprite_inspection", "aseprite_slice_authoring"
            )
        ),
        invoke_kernel=invoke,
        target_files=LocalTargetFiles(),
    )
    request = SliceSetRequest(
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        target={"slice_name": "before"},
        properties={"name": "after"},
    )
    return services, request, source, target, stages


def test_valid_reopened_snapshot_can_publish(tmp_path):
    services, request, source, target, stages = staging(tmp_path, response())
    result = set_slice(request, services)
    assert result.previous_slice.name == "before" and result.slices[0].name == "after"
    assert (
        target.read_bytes() == b"native output" and source.read_bytes() == b"original"
    )
    assert not stages[0].exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "verified",
        "operation",
        "count",
        "frame_count",
        "index",
        "selected_index",
        "duplicate_name",
        "coverage",
        "keys",
        "rejection",
    ],
)
def test_inconsistent_slice_response_cannot_publish(tmp_path, corruption):
    evidence = response()
    after = evidence["snapshot"]
    if corruption == "verified":
        evidence["persisted_reopen_verified"] = False
    elif corruption == "operation":
        evidence["operation"] = "add"
    elif corruption == "count":
        after["slices"] = []
    elif corruption == "frame_count":
        after["frame_count"] = 3
    elif corruption == "index":
        after["slices"][0]["slice_index"] = 2
    elif corruption == "selected_index":
        evidence["selected_before_index"] = True
    elif corruption == "duplicate_name":
        evidence["before"]["slices"].append(
            {**deepcopy(evidence["before"]["slices"][0]), "slice_index": 2}
        )
        after["slices"].append({**deepcopy(after["slices"][0]), "slice_index": 2})
    elif corruption == "coverage":
        after["slices"][0]["keys"][0]["effective_frame_range"]["to_frame"] = 1
    elif corruption == "keys":
        after["slices"][0]["keys"].append(deepcopy(after["slices"][0]["keys"][0]))
    elif corruption == "rejection":
        evidence["rejection"] = {"code": "invented", "message": "refused"}
    services, request, source, target, stages = staging(tmp_path, evidence)
    with pytest.raises(RuntimeIssue) as caught:
        set_slice(request, services)
    assert caught.value.kind == "response_malformed"
    assert target.read_bytes() == b"existing" and source.read_bytes() == b"original"
    assert not stages[0].exists()


def test_interruption_discards_staged_slice_file(tmp_path):
    services, request, source, target, stages = staging(
        tmp_path, response(), crash=True
    )
    with pytest.raises(RuntimeError, match="interrupted"):
        set_slice(request, services)
    assert target.read_bytes() == b"existing" and source.read_bytes() == b"original"
    assert not stages[0].exists()


def test_source_alias_changed_before_commit_refuses_publication(tmp_path):
    services, request, _, target, stages = staging(tmp_path, response(), redirect=True)
    with pytest.raises(RuntimeIssue) as caught:
        set_slice(request, services)
    assert caught.value.kind == "target_commit_failed"
    assert target.read_bytes() == b"existing" and not stages[0].exists()
