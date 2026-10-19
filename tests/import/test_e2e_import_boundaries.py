"""Real native import evidence must pass every publication boundary."""

import hashlib
import json
import os

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import invoke
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.png_input import decode_png_input
from spa.application.dispatch import dispatch
from spa.application.failure_registry import FAILURE_CODES
from spa.authoring.raster.image_import import IMAGE_IMPORT_OPERATIONS
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import OperationServices, RuntimeIssue, TargetCommitEvidence
from tests.host_permissions import symlink_creation_permission
from tests.support import process_diagnostics, spa

from .test_e2e_image_import import _create
from .test_e2e_image_import import runtime as runtime  # noqa: PLC0414

pytestmark = pytest.mark.e2e


class _ObservedTargetFiles(LocalTargetFiles):
    def __init__(self):
        self.stages = []
        self.commits = []
        self.discards = []

    def staged_path(self, target):
        staged = super().staged_path(target)
        self.stages.append(staged)
        return staged

    def commit(self, staged, target, *, overwrite):
        self.commits.append(staged)
        return super().commit(staged, target, overwrite=overwrite)

    def discard(self, staged):
        self.discards.append(staged)
        super().discard(staged)


def _request(source, raster, target):
    return {
        "aseprite": os.environ["SPA_TEST_ASEPRITE"],
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": True,
        "raster_file": str(raster),
        "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
        "position": {"x": -1, "y": 1},
    }


def _dispatch(source, raster, target, runtime, files, invoker):
    services = OperationServices(
        probe_runtime=lambda _: runtime,
        invoke_kernel=invoker,
        target_files=files,
        artifact_files=LocalArtifactFiles(),
        decode_png_input=decode_png_input,
    )
    result = dispatch(
        IMAGE_IMPORT_OPERATIONS[0],
        json.dumps(_request(source, raster, target)),
        {},
        services,
        FAILURE_CODES,
    )
    return result.model_dump(mode="json")


def _inputs(tmp_path, runtime):
    source, raster, target = (
        tmp_path / name for name in ("source.aseprite", "input.png", "target.aseprite")
    )
    _create(runtime, source)
    target.write_bytes(source.read_bytes())
    Image.new("RGBA", (2, 1), (17, 31, 53, 128)).save(raster)
    return source, raster, target


def _assert_unpublished(source, raster, target, original, files):
    assert (source.read_bytes(), raster.read_bytes(), target.read_bytes()) == original
    assert len(files.stages) == 1
    assert files.discards == files.stages
    assert all(not stage.exists() for stage in files.stages)
    assert not list(target.parent.glob(".*.staged.aseprite"))


def test_consumed_png_remains_frozen_when_original_changes_before_native(
    tmp_path, runtime
):
    source, raster, target = _inputs(tmp_path, runtime)
    original_png, original_source = raster.read_bytes(), source.read_bytes()
    original_pixels = decode_png_input(original_png).rgba_bytes
    files = _ObservedTargetFiles()
    calls = []

    def changed_input(observation, handler, payload, timeout):
        assert bytes.fromhex(payload["raster_bytes"]) == original_png
        Image.new("RGBA", (3, 2), (200, 150, 100, 255)).save(raster)
        calls.append(raster.read_bytes())
        return invoke(observation, handler, payload, timeout)

    result = _dispatch(source, raster, target, runtime, files, changed_input)
    assert result["status"] == "success", result
    assert len(calls) == 1 and calls[0] != original_png
    assert result["raster_file"]["sha256"] == hashlib.sha256(original_png).hexdigest()
    assert result["raster_file"]["byte_size"] == len(original_png)
    assert result["image"]["width"] == 2 and result["image"]["height"] == 1
    assert result["image"]["rgba_content_digest"]["value"] == fnv1a64(original_pixels)
    assert source.read_bytes() == original_source
    assert raster.read_bytes() == calls[0]
    assert files.commits == files.stages == files.discards
    assert all(not stage.exists() for stage in files.stages)
    read = spa(
        "image",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(target),
                "source": {
                    "kind": "individual",
                    "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
                    "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
                },
            }
        ),
    )
    assert read.returncode == 0, process_diagnostics(read)
    row = json.loads(read.stdout)["snapshot"]["rows"][0]
    pixels = bytes(
        component
        for run in row
        for _ in range(run["length"])
        for component in (
            run["color"]["red"],
            run["color"]["green"],
            run["color"]["blue"],
            run["color"]["alpha"],
        )
    )
    assert pixels == original_pixels


def test_target_publication_failure_after_native_success_preserves_inputs(
    tmp_path, runtime
):
    source, raster, target = _inputs(tmp_path, runtime)
    original = source.read_bytes(), raster.read_bytes(), target.read_bytes()

    class FailingTargetFiles(_ObservedTargetFiles):
        def commit(self, staged, target, *, overwrite):
            assert staged.is_file() and staged.read_bytes() != original[0]
            self.commits.append(staged)
            raise RuntimeIssue(
                "target_commit_failed",
                "Injected publication failure",
                TargetCommitEvidence(str(target), "replace_failed"),
            )

    files = FailingTargetFiles()
    result = _dispatch(source, raster, target, runtime, files, invoke)
    assert result.get("code") == "target_commit_failed", result
    assert result["details"]["reason"] == "replace_failed"
    assert files.commits == files.stages
    _assert_unpublished(source, raster, target, original, files)


def test_changed_raster_alias_before_commit_refuses_and_discards_native_stage(
    tmp_path, runtime
):
    source, raster, target = _inputs(tmp_path, runtime)
    original_source, original_png, original_target = (
        source.read_bytes(),
        raster.read_bytes(),
        target.read_bytes(),
    )
    files = _ObservedTargetFiles()

    def retarget_input(observation, handler, payload, timeout):
        observed = invoke(observation, handler, payload, timeout)
        assert observed.payload.get("persisted_reopen_verified") is True, (
            observed.payload
        )
        raster.rename(tmp_path / "preserved-input.png")
        with symlink_creation_permission():
            raster.symlink_to(target.name)
        return observed

    result = _dispatch(source, raster, target, runtime, files, retarget_input)
    assert result.get("code") == "image_import_incompatible", result
    assert result["details"]["reason"] == "output_alias"
    assert source.read_bytes() == original_source
    assert (tmp_path / "preserved-input.png").read_bytes() == original_png
    assert target.read_bytes() == original_target
    assert raster.is_symlink()
    assert not files.commits
    assert files.discards == files.stages
    assert all(not stage.exists() for stage in files.stages)
