"""Native Color Mode conversions through the installed SPA surface."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import inject_palette_change, process_diagnostics, spa

pytestmark = pytest.mark.e2e


def run(*command: str, **request: object) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def native_script(runtime, script: str, **params: object) -> None:
    with tempfile.TemporaryDirectory(prefix="spa-color-mode-fixture-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        arguments = [str(prepared.executable), "--batch"]
        for name, value in params.items():
            arguments.extend(["--script-param", f"{name}={value}"])
        result = subprocess.run(
            [*arguments, "--script", str(Path(__file__).parent / "fixtures" / script)],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)


def make_source(
    source: Path, runtime, mode: str = "rgb", *, scene: bool = False
) -> None:
    native_script(
        runtime, "scene.lua" if scene else "source.lua", source=source, mode=mode
    )
    if scene:
        inject_palette_change(
            source,
            [
                (40, 90, 120, 255),
                (40, 60, 220, 255),
                (220, 150, 40, 128),
                (0, 0, 0, 0),
                (230, 80, 90, 255),
                (255, 255, 255, 255),
            ],
            frame_number=3,
        )


def convert(source: Path, target: Path, conversion: dict) -> tuple[int, dict]:
    return run(
        "sprite",
        "change-color-mode",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        conversion=conversion,
    )


def test_rgb_to_grayscale_preserves_source_and_reports_reopened_images(
    tmp_path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    original = source.read_bytes()
    code, result = convert(
        source,
        target,
        {
            "source_color_mode": "rgb",
            "target": {"color_mode": "grayscale", "to_gray": "luma"},
        },
    )
    assert code == 0, result
    assert result["source_color_mode"] == "rgb"
    assert result["target_color_mode"] == "grayscale"
    assert result["changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert result["before"]["images"][0]["bytes_per_pixel"] == 4
    assert result["after"]["images"][0]["bytes_per_pixel"] == 2
    assert (
        result["before"]["images"][0]["content"]
        != result["after"]["images"][0]["content"]
    )
    code, inspected = run(
        "sprite", "get", sprite_file=str(target), inspection_scope=["cels", "palettes"]
    )
    assert code == 0, inspected
    assert inspected["metadata"]["color_mode"] == "grayscale"
    assert source.read_bytes() == original


def conversion_for(source: str, target: str) -> dict:
    options: dict = {"color_mode": target}
    if source != target:
        if target == "grayscale":
            options["to_gray"] = "luma"
        if target == "indexed":
            options.update(
                rgb_map_algorithm="default", color_best_fit_criteria="default"
            )
            if source == "rgb":
                options["dithering"] = {"algorithm": "none"}
    return {"source_color_mode": source, "target": options}


@pytest.mark.parametrize("source_mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("target_mode", ["rgb", "grayscale", "indexed"])
def test_every_color_mode_pair(tmp_path, runtime, source_mode, target_mode):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, source_mode)
    original = source.read_bytes()
    code, result = convert(source, target, conversion_for(source_mode, target_mode))
    assert code == 0, result
    assert result["after"]["color_mode"] == target_mode
    assert result["changed"] == (source_mode != target_mode)
    if source_mode == target_mode:
        assert result["before"] == result["after"]
        assert result["mapping"] is None and result["dithering"] is None
    elif target_mode == "indexed":
        assert result["mapping"] == {
            "requested_rgb_map_algorithm": "default",
            "effective_rgb_map_algorithm": "octree",
            "color_best_fit_criteria": "default",
        }
        assert (
            sum(
                item["pixel_count"]
                for item in result["after"]["images"][0]["palette_indices"]
            )
            == 3
        )
        if source_mode == "rgb":
            assert result["dithering"]["effective_algorithm"] == "none"
        else:
            assert result["dithering"] is None
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "algorithm,matrix,size",
    [
        ("ordered", None, 8),
        ("old", None, 8),
        ("ordered", {"kind": "installed", "id": "bayer4x4"}, 4),
        ("old", {"kind": "installed", "id": "bayer2x2"}, 2),
        ("ordered", {"kind": "installed", "id": "bayer8x8"}, 8),
    ],
)
def test_dithering_matrix_resolution(tmp_path, runtime, algorithm, matrix, size):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = {"algorithm": algorithm}
    if matrix is not None:
        conversion["target"]["dithering"]["matrix"] = matrix
    code, result = convert(source, target, conversion)
    assert code == 0, result
    facts = result["dithering"]
    assert facts["effective_algorithm"] == algorithm
    assert facts["matrix"]["requested"] == matrix
    assert facts["matrix"]["width"] == facts["matrix"]["height"] == size
    assert facts["matrix"]["identity"] == f"bayer{size}x{size}"
    assert facts["matrix"]["provenance"] == (
        "installed" if matrix else "native-default"
    )


def test_standalone_and_plan_share_the_conversion_owner(tmp_path, runtime):
    source, standalone, planned = [
        tmp_path / f"{name}.aseprite" for name in ("source", "standalone", "plan")
    ]
    make_source(source, runtime)
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = {
        "algorithm": "ordered",
        "matrix": {"kind": "installed", "id": "bayer4x4"},
    }
    code, one = convert(source, standalone, conversion)
    assert code == 0, one
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(planned),
            "steps": [
                {
                    "operation": "sprite change-color-mode",
                    "input": {"conversion": conversion},
                }
            ],
            "postconditions": {"color_mode": "indexed"},
        },
    )
    assert code == 0, result
    step = result["steps"][0]["result"]
    assert step["persisted_reopen_verified"] is False
    for field in ("before", "after", "mapping", "dithering", "changed"):
        assert step[field] == one[field]
    assert result["persisted_reopen_verified"] is True
    assert result["final_sprite"]["metadata"]["color_mode"] == "indexed"


@pytest.mark.parametrize(
    "source_mode,target_mode",
    [
        ("rgb", "indexed"),
        ("indexed", "rgb"),
        ("indexed", "grayscale"),
        ("grayscale", "indexed"),
        ("rgb", "grayscale"),
        ("grayscale", "rgb"),
        ("indexed", "indexed"),
    ],
)
def test_complete_sprite_images_palette_basis_and_links(
    tmp_path, runtime, source_mode, target_mode
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, source_mode, scene=True)
    original = source.read_bytes()
    code, result = convert(source, target, conversion_for(source_mode, target_mode))
    assert code == 0, result
    before, after = result["before"], result["after"]
    assert len(before["palettes"]["palette_changes"]) == 2
    assert {item["kind"] for item in after["images"]} == {"cel", "tile", "tilemap"}
    assert len(before["tilesets"]) == len(after["tilesets"]) == 2
    assert [cel["image_number"] for cel in before["cels"]] == [
        cel["image_number"] for cel in after["cels"]
    ]
    assert any(cel["is_background"] for cel in after["cels"])
    assert len({cel["image_number"] for cel in before["cels"]}) < len(before["cels"])
    assert {
        image["palette_frame_number"]
        for image in before["images"]
        if image["kind"] == "cel"
    } == {1, 3}
    assert {
        image["conversion_frame_number"]
        for image in before["images"]
        if image["kind"] == "tile"
    } == {1}
    for old, new in zip(before["images"], after["images"], strict=True):
        if old["kind"] == "tilemap":
            assert old == new
        else:
            assert (
                new["bytes_per_pixel"]
                == {"rgb": 4, "grayscale": 2, "indexed": 1}[target_mode]
            )
    if source_mode != target_mode and target_mode == "indexed":
        assert all(cel["opacity"] == 255 for cel in after["cels"])
        assert after["transparent_color_index"] == 3
    if source_mode != target_mode and target_mode == "grayscale":
        assert len(after["palettes"]["palette_changes"]) == 1
        assert len(after["palettes"]["palette_changes"][0]["entries"]) == 256
    assert source.read_bytes() == original


def assert_native_reference(tmp_path, runtime, source, result, options):
    options_file, reference, receipt = [
        tmp_path / name
        for name in ("options.json", "reference.aseprite", "receipt.aseprite")
    ]
    options_file.write_text(json.dumps(options))
    native_script(
        runtime,
        "native_reference.lua",
        source=source,
        target=reference,
        options=options_file,
    )
    mode = result["target_color_mode"]
    code, observed = convert(reference, receipt, conversion_for(mode, mode))
    assert code == 0, observed
    assert observed["after"] == result["after"]


@pytest.mark.parametrize("source_mode", ["rgb", "grayscale"])
@pytest.mark.parametrize("mapping", ["default", "rgb5a3", "octree"])
@pytest.mark.parametrize(
    "criteria", ["default", "rgb", "linearizedRGB", "ciexyz", "cielab"]
)
def test_mapping_choices_match_direct_native_command(
    tmp_path, runtime, source_mode, mapping, criteria
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, source_mode, scene=True)
    conversion = conversion_for(source_mode, "indexed")
    conversion["target"].update(
        rgb_map_algorithm=mapping, color_best_fit_criteria=criteria
    )
    code, result = convert(source, target, conversion)
    assert code == 0, result
    assert result["mapping"]["requested_rgb_map_algorithm"] == mapping
    assert result["mapping"]["color_best_fit_criteria"] == criteria
    assert_native_reference(
        tmp_path,
        runtime,
        source,
        result,
        {
            "format": "indexed",
            "rgbmap": mapping,
            "fitCriteria": criteria,
            "dithering": "none",
        },
    )


@pytest.mark.parametrize("source_mode", ["rgb", "indexed"])
@pytest.mark.parametrize("to_gray", ["luma", "hsv", "hsl"])
def test_to_gray_choices_match_direct_native_command(
    tmp_path, runtime, source_mode, to_gray
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, source_mode, scene=True)
    conversion = conversion_for(source_mode, "grayscale")
    conversion["target"]["to_gray"] = to_gray
    code, result = convert(source, target, conversion)
    assert code == 0, result
    assert_native_reference(
        tmp_path, runtime, source, result, {"format": "gray", "toGray": to_gray}
    )


@pytest.mark.parametrize("factor", [0, 0.345, 1])
def test_error_diffusion_factor_matches_native_and_reports_effective_percent(
    tmp_path, runtime, factor
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime, scene=True)
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = {
        "algorithm": "error-diffusion",
        "dithering_factor": factor,
    }
    code, result = convert(source, target, conversion)
    assert code == 0, result
    assert result["dithering"]["dithering_factor"] == factor
    assert result["dithering"]["effective_factor_percent"] == int(factor * 100)
    assert result["dithering"]["matrix"] is None
    assert_native_reference(
        tmp_path,
        runtime,
        source,
        result,
        {
            "format": "indexed",
            "rgbmap": "default",
            "fitCriteria": "default",
            "dithering": "error-diffusion",
            "ditheringFactor": factor,
        },
    )


@pytest.mark.parametrize("algorithm", ["ordered", "old"])
def test_file_matrix_matches_installed_matrix_and_native_pixels(
    tmp_path, runtime, algorithm
):
    source = tmp_path / "source.aseprite"
    make_source(source, runtime, scene=True)
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = {
        "algorithm": algorithm,
        "matrix": {"kind": "installed", "id": "bayer4x4"},
    }
    code, installed = convert(source, tmp_path / "installed.aseprite", conversion)
    assert code == 0, installed
    path = installed["dithering"]["matrix"]["resolved_path"]
    conversion["target"]["dithering"]["matrix"] = {"kind": "file", "path": path}
    code, explicit = convert(source, tmp_path / "explicit.aseprite", conversion)
    assert code == 0, explicit
    assert explicit["after"] == installed["after"]
    assert explicit["dithering"]["matrix"]["provenance"] == "file"
    assert explicit["dithering"]["matrix"]["requested"]["path"] == path
    assert_native_reference(
        tmp_path,
        runtime,
        source,
        explicit,
        {
            "format": "indexed",
            "rgbmap": "default",
            "fitCriteria": "default",
            "dithering": algorithm,
            "ditheringMatrix": path,
        },
    )


@pytest.mark.parametrize(
    "failure", ["missing-id", "missing-file", "invalid", "unreadable", "wrong-source"]
)
@pytest.mark.parametrize("via_plan", [False, True])
def test_preflight_failure_preserves_existing_source_and_target(
    tmp_path, runtime, failure, via_plan
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"existing target must survive")
    conversion = conversion_for("rgb", "indexed")
    matrix = tmp_path / "matrix.bmp"
    if failure == "missing-id":
        selected = {"kind": "installed", "id": "Bayer8x8-does-not-exist"}
    else:
        selected = {"kind": "file", "path": str(matrix)}
        if failure in {"invalid", "unreadable"}:
            matrix.write_bytes(b"not a native image")
        if failure == "unreadable":
            matrix.chmod(0)
    conversion["target"]["dithering"] = {"algorithm": "ordered", "matrix": selected}
    if failure == "wrong-source":
        conversion = conversion_for("indexed", "rgb")
    if via_plan:
        code, result = run(
            "plan",
            "run",
            plan={
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "overwrite": True,
                "steps": [
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 2, "duration_ms": 100},
                    },
                    {
                        "operation": "sprite change-color-mode",
                        "input": {"conversion": conversion},
                    },
                ],
            },
        )
    else:
        code, result = run(
            "sprite",
            "change-color-mode",
            source_sprite_file=str(source),
            target_sprite_file=str(target),
            in_place=False,
            overwrite=True,
            conversion=conversion,
        )
    assert code != 0, result
    assert result["code"] == (
        "color_mode_mismatch"
        if failure == "wrong-source"
        else "dithering_matrix_invalid"
    ), result
    if via_plan:
        assert result["details"]["step_number"] == 2
    if failure in {"unreadable", "invalid"}:
        assert result["details"]["reason"] == failure
    assert source.read_bytes() == original
    assert target.read_bytes() == b"existing target must survive"
    assert not list(tmp_path.glob("*.stage*"))


def test_ambiguous_installed_matrix_is_rejected_before_publication(tmp_path, runtime):
    from dataclasses import replace

    from spa.adapters.aseprite.aseprite import invoke
    from spa.adapters.files import LocalTargetFiles
    from spa.authoring.color.color_mode import ColorModeRequest, change_color_mode
    from spa.contracts.ports import OperationIssue, OperationServices

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    data = tmp_path / "data"
    data.mkdir()
    for child in Path(runtime.resource_path).parent.iterdir():
        if child.name != "extensions":
            (data / child.name).symlink_to(child, target_is_directory=child.is_dir())
    for name in ("first", "second"):
        extension = data / "extensions" / name
        extension.mkdir(parents=True)
        (extension / "package.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "version": "1.0.0",
                    "contributes": {
                        "ditheringMatrices": [
                            {"id": "duplicate", "path": "matrix.bmp"},
                        ]
                    },
                }
            )
        )
    selected = replace(runtime, resource_path=str(data / "gui.xml"))
    services = OperationServices(lambda _request: selected, invoke, LocalTargetFiles())
    conversion = conversion_for("rgb", "indexed")
    conversion["target"]["dithering"] = {
        "algorithm": "ordered",
        "matrix": {"kind": "installed", "id": "duplicate"},
    }
    request = ColorModeRequest.model_validate(
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "conversion": conversion,
        }
    )
    with pytest.raises(OperationIssue) as failure:
        change_color_mode(request, services)
    assert failure.value.code == "dithering_matrix_invalid"
    assert failure.value.details.reason == "ambiguous"
    assert len(failure.value.details.matches) == 2
    assert not target.exists()


def test_plan_create_then_convert_uses_final_mode_for_postconditions(tmp_path):
    target = tmp_path / "target.aseprite"
    code, result = run(
        "plan",
        "run",
        plan={
            "target_sprite_file": str(target),
            "steps": [
                {
                    "operation": "sprite create",
                    "input": {
                        "width": 2,
                        "height": 2,
                        "color_mode": "rgb",
                        "initial_layer": {"kind": "transparent"},
                    },
                },
                {
                    "operation": "sprite change-color-mode",
                    "input": {"conversion": conversion_for("rgb", "grayscale")},
                },
                {
                    "operation": "sprite change-color-mode",
                    "input": {"conversion": conversion_for("grayscale", "indexed")},
                },
                {"operation": "sprite get", "input": {"inspection_scope": ["cels"]}},
            ],
            "postconditions": {"color_mode": "indexed"},
        },
    )
    assert code == 0, result
    assert result["steps"][0]["result"]["sprite"]["metadata"]["color_mode"] == "rgb"
    assert result["final_sprite"]["metadata"]["color_mode"] == "indexed"
    assert result["persisted_reopen_verified"] is True


def test_failed_postcondition_after_conversion_rolls_back_target(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    make_source(source, runtime)
    original = source.read_bytes()
    target.write_bytes(b"previous target")
    code, result = run(
        "plan",
        "run",
        plan={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "overwrite": True,
            "steps": [
                {
                    "operation": "sprite change-color-mode",
                    "input": {"conversion": conversion_for("rgb", "grayscale")},
                }
            ],
            "postconditions": {"color_mode": "rgb"},
        },
    )
    assert code != 0 and result["code"] == "kernel_execution_failed", result
    assert source.read_bytes() == original
    assert target.read_bytes() == b"previous target"


def test_in_place_conversion_commits_only_after_verified_reopen(tmp_path, runtime):
    source = tmp_path / "source.aseprite"
    make_source(source, runtime)
    original = source.read_bytes()
    code, result = run(
        "sprite",
        "change-color-mode",
        source_sprite_file=str(source),
        target_sprite_file=str(source),
        in_place=True,
        overwrite=True,
        conversion=conversion_for("rgb", "indexed"),
    )
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert source.read_bytes() != original
    stable = source.read_bytes()
    code, rejected = run(
        "sprite",
        "change-color-mode",
        source_sprite_file=str(source),
        target_sprite_file=str(source),
        in_place=True,
        overwrite=True,
        conversion=conversion_for("rgb", "grayscale"),
    )
    assert code != 0 and rejected["code"] == "color_mode_mismatch", rejected
    assert source.read_bytes() == stable
