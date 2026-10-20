"""Real native import evidence must pass every publication boundary."""

import hashlib

import pytest
from PIL import Image

from spa.adapters.aseprite.aseprite import invoke
from spa.adapters.png_input import decode_png_input
from spa.contracts.digest import fnv1a64
from spa.contracts.ports import RuntimeIssue, TargetCommitEvidence
from tests.host_permissions import symlink_creation_permission
from tests.native_invocation import expect_success

from .support import (
    ObservedTargetFiles,
    assert_unpublished,
    dispatch_import,
    import_inputs,
)

pytestmark = pytest.mark.e2e


def test_consumed_png_remains_frozen_when_original_changes_before_native(
    tmp_path, runtime
):
    source, raster, target = import_inputs(tmp_path, runtime)
    original_png, original_source = raster.read_bytes(), source.read_bytes()
    original_pixels = decode_png_input(original_png).rgba_bytes
    files = ObservedTargetFiles()
    calls = []

    def changed_input(observation, handler, payload, timeout):
        assert bytes.fromhex(payload["raster_bytes"]) == original_png
        Image.new("RGBA", (3, 2), (200, 150, 100, 255)).save(raster)
        calls.append(raster.read_bytes())
        return invoke(observation, handler, payload, timeout)

    result = dispatch_import(source, raster, target, runtime, files, changed_input)
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
    read = expect_success(
        "image get",
        {
            "sprite_file": str(target),
            "source": {
                "kind": "individual",
                "target": {"layer": {"layer_path": [1]}, "frame_number": 2},
                "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
            },
        },
    )
    row = read["snapshot"]["rows"][0]
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
    source, raster, target = import_inputs(tmp_path, runtime)
    original = source.read_bytes(), raster.read_bytes(), target.read_bytes()

    class FailingTargetFiles(ObservedTargetFiles):
        def commit(self, staged, target, *, overwrite):
            assert staged.is_file() and staged.read_bytes() != original[0]
            self.commits.append(staged)
            raise RuntimeIssue(
                "target_commit_failed",
                "Injected publication failure",
                TargetCommitEvidence(str(target), "replace_failed"),
            )

    files = FailingTargetFiles()
    result = dispatch_import(source, raster, target, runtime, files, invoke)
    assert result.get("code") == "target_commit_failed", result
    assert result["details"]["reason"] == "replace_failed"
    assert files.commits == files.stages
    assert_unpublished(source, raster, target, original, files)


def test_changed_raster_alias_before_commit_refuses_and_discards_native_stage(
    tmp_path, runtime
):
    source, raster, target = import_inputs(tmp_path, runtime)
    original_source, original_png, original_target = (
        source.read_bytes(),
        raster.read_bytes(),
        target.read_bytes(),
    )
    files = ObservedTargetFiles()

    def retarget_input(observation, handler, payload, timeout):
        observed = invoke(observation, handler, payload, timeout)
        assert observed.payload.get("persisted_reopen_verified") is True, (
            observed.payload
        )
        raster.rename(tmp_path / "preserved-input.png")
        with symlink_creation_permission():
            raster.symlink_to(target.name)
        return observed

    result = dispatch_import(source, raster, target, runtime, files, retarget_input)
    assert result.get("code") == "image_import_incompatible", result
    assert result["details"]["reason"] == "output_alias"
    assert source.read_bytes() == original_source
    assert (tmp_path / "preserved-input.png").read_bytes() == original_png
    assert target.read_bytes() == original_target
    assert raster.is_symlink()
    assert not files.commits
    assert files.discards == files.stages
    assert all(not stage.exists() for stage in files.stages)
