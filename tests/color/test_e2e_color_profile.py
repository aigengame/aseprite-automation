"""Color Profile commands preserve or transform native stored color facts."""

import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def runtime():
    return probe(
        RuntimeRequest(aseprite=os.environ["SPA_TEST_ASEPRITE"]), PROBE_RESOURCES
    )


def _require_conversion(runtime) -> None:
    if "aseprite_convert_color_profile" not in runtime.verified_capabilities:
        # The selected macOS bundle must retain its proven native converter.
        assert sys.platform == "linux", "expected native Color Profile conversion"
        pytest.skip("selected Linux runtime has no native Color Profile converter")


def _native(runtime, source: Path, **params: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="spa-profile-test-") as work:
        prepared = prepare_invocation(
            Path(runtime.canonical_path), Path(runtime.resource_path), Path(work)
        )
        arguments = [str(prepared.executable), "--batch"]
        for key, value in {"source": str(source), **params}.items():
            arguments.extend(["--script-param", f"{key}={value}"])
        result = subprocess.run(
            [
                *arguments,
                "--script",
                str(Path(__file__).parent / "fixtures/profile_sprite.lua"),
            ],
            env=prepared.environment,
            text=True,
            capture_output=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)
    return json.loads(result.stdout)


def _run(command: str, source: Path, target: Path, profile: dict, **extra: object):
    result = spa(
        "sprite",
        command,
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "source_sprite_file": str(source),
                "target_sprite_file": str(target),
                "in_place": source == target,
                "overwrite": True,
                "profile": profile,
                **extra,
            }
        ),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def test_assign_none_preserves_stored_colors_and_persists_profile(
    tmp_path: Path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    before = _native(runtime, source, action="create")
    original = source.read_bytes()
    code, result = _run("assign-color-profile", source, target, {"kind": "none"})
    assert code == 0, result
    assert result["source_profile"]["kind"] == "srgb"
    assert result["requested_profile"]["kind"] == "none"
    assert result["effective_profile"]["kind"] == "none"
    assert result["profile_changed"] is True
    assert result["persisted_reopen_verified"] is True
    assert not any(item["changed"] for item in result["images"] + result["palettes"])
    after = _native(runtime, target, action="observe")
    assert _encoded_profile(target) == "none"
    assert after["pixels"] == before["pixels"]
    assert after["entries"] == before["entries"]
    assert source.read_bytes() == original


def _encoded_profile(path: Path) -> str:
    data = path.read_bytes()
    offset = 144
    frame_end = 128 + struct.unpack_from("<I", data, 128)[0]
    while offset < frame_end:
        size, kind = struct.unpack_from("<IH", data, offset)
        if kind == 0x2007:
            return {0: "none", 1: "srgb", 2: "icc"}[
                struct.unpack_from("<H", data, offset + 6)[0]
            ]
        offset += size
    return "none"


def _plan(source: Path, target: Path, steps: list[dict]):
    result = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "target_sprite_file": str(target),
                    "in_place": source == target,
                    "overwrite": True,
                    "steps": steps,
                },
            }
        ),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def test_assign_plan_uses_step_start_profile_and_final_none_persistence(
    tmp_path: Path, runtime
):
    source, target = tmp_path / "source.aseprite", tmp_path / "plan.aseprite"
    _native(runtime, source, action="create")
    steps = [
        {
            "operation": "sprite assign-color-profile",
            "input": {"profile": {"kind": kind}},
        }
        for kind in ["none", "srgb", "none"]
    ]
    code, result = _plan(source, target, steps)
    assert code == 0, result
    assert result["persisted_reopen_verified"] is True
    assert [item["result"]["source_profile"]["kind"] for item in result["steps"]] == [
        "srgb",
        "none",
        "srgb",
    ]
    assert all(
        item["result"]["persisted_reopen_verified"] is False for item in result["steps"]
    )
    assert _encoded_profile(target) == "none"
    code, repeat = _run("assign-color-profile", target, target, {"kind": "none"})
    assert code == 0 and not repeat["profile_changed"], repeat
    assert repeat["source_profile"]["kind"] == "none"


def _linear_icc(path: Path) -> bytes:
    # Test-only linear-light RGB profile: retain LittleCMS primaries/white point,
    # replace the shared RGB tone-response tag with ICC parametric gamma 1.0.
    from PIL import ImageCms

    data = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    for index in range(struct.unpack_from(">I", data, 128)[0]):
        record = 132 + 12 * index
        tag, offset, _ = struct.unpack_from(">4sII", data, record)
        if tag in {b"rTRC", b"gTRC", b"bTRC"}:
            data[offset : offset + 16] = struct.pack(">4sIHHI", b"para", 0, 0, 0, 65536)
            struct.pack_into(">I", data, record + 8, 16)
    path.write_bytes(data)
    return bytes(data)


@pytest.mark.parametrize("profile_kind", ["linear_rgb", "lab"])
def test_assign_icc_reports_frozen_input_and_preserves_pixels(
    tmp_path: Path, runtime, profile_kind: str
):
    import hashlib

    from PIL import ImageCms

    source, target = tmp_path / "source.aseprite", tmp_path / "icc.aseprite"
    before = _native(runtime, source, action="create")
    icc = tmp_path / "linear.icc"
    if profile_kind == "linear_rgb":
        contents = _linear_icc(icc)
    else:
        contents = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
        icc.write_bytes(contents)
    code, result = _run(
        "assign-color-profile", source, target, {"kind": "icc", "icc_file": str(icc)}
    )
    assert code == 0, result
    assert (
        result["requested_profile"]["kind"]
        == result["effective_profile"]["kind"]
        == "icc"
    )
    assert result["icc_file"] == {
        "path": str(icc),
        "byte_size": len(contents),
        "sha256": hashlib.sha256(contents).hexdigest(),
        "native_name": result["effective_profile"]["name"],
        "matches_effective_profile": True,
    }
    after = _native(runtime, target, action="observe", expected_icc=str(icc))
    assert _encoded_profile(target) == "icc"
    assert after["matches_requested_icc"] is True
    assert before["pixels"] == after["pixels"] and before["entries"] == after["entries"]
    plan_target = tmp_path / "plan-assigned.aseprite"
    code, planned = _plan(
        source,
        plan_target,
        [
            {
                "operation": "sprite assign-color-profile",
                "input": {"profile": {"kind": "icc", "icc_file": str(icc)}},
            }
        ],
    )
    assert code == 0, planned
    assert planned["steps"][0]["result"]["icc_file"] == result["icc_file"]
    assert (
        _native(runtime, plan_target, action="observe", expected_icc=str(icc)) == after
    )


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_convert_icc_matches_independent_native_conversion_and_reports_changes(
    tmp_path: Path, runtime, mode: str
):
    _require_conversion(runtime)
    source, target, oracle = (
        tmp_path / name
        for name in ["source.aseprite", "converted.aseprite", "oracle.aseprite"]
    )
    before = _native(runtime, source, action="create", mode=mode)
    icc = tmp_path / "linear.icc"
    _linear_icc(icc)
    code, result = _run(
        "convert-color-profile", source, target, {"kind": "icc", "icc_file": str(icc)}
    )
    assert code == 0, result
    expected = _native(
        runtime, source, action="convert", icc=str(icc), output=str(oracle)
    )
    actual = _native(runtime, target, action="observe")
    assert actual == _native(runtime, oracle, action="observe") == expected
    assert _encoded_profile(target) == "icc"
    assert result["images"][0]["changed"] == (before["pixels"] != actual["pixels"])
    assert result["palettes"][0]["changed"] == (before["entries"] != actual["entries"])
    # Independent fixture has midtones. RGB must actually transform; Indexed keeps indexes.
    if mode == "rgb":
        assert before["pixels"] != actual["pixels"]
        assert before["entries"] != actual["entries"]
    if mode == "indexed":
        assert before["pixels"] == actual["pixels"]
        assert before["entries"] != actual["entries"]
    if mode == "grayscale":
        assert before["entries"] == actual["entries"]


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_assign_and_convert_cover_noops_and_native_srgb_target(
    tmp_path: Path, runtime, mode: str
):
    _require_conversion(runtime)
    source, assigned, converted = (
        tmp_path / name
        for name in ["source.aseprite", "assigned.aseprite", "converted.aseprite"]
    )
    before = _native(runtime, source, action="create", mode=mode)
    for command in ["assign-color-profile", "convert-color-profile"]:
        code, noop = _run(command, source, source, {"kind": "srgb"})
        assert code == 0 and not noop["profile_changed"], noop
        assert not any(item["changed"] for item in noop["images"] + noop["palettes"])
    icc = tmp_path / "linear.icc"
    _linear_icc(icc)
    code, result = _run(
        "assign-color-profile", source, assigned, {"kind": "icc", "icc_file": str(icc)}
    )
    assert code == 0, result
    assert _native(runtime, assigned, action="observe")["pixels"] == before["pixels"]
    code, result = _run("convert-color-profile", assigned, converted, {"kind": "srgb"})
    assert code == 0 and result["source_profile"]["kind"] == "icc", result
    assert result["effective_profile"]["kind"] == _encoded_profile(converted) == "srgb"
    assert result["icc_file"] is None
    code, _ = _run("assign-color-profile", assigned, assigned, {"kind": "none"})
    assert code == 0
    code, result = _run("convert-color-profile", assigned, assigned, {"kind": "srgb"})
    assert code == 0 and result["source_profile"]["kind"] == "none", result
    assert _native(runtime, assigned, action="observe")["pixels"] == before["pixels"]


def test_convert_preserves_linked_cels_and_reports_all_palette_changes_and_tiles(
    tmp_path: Path, runtime
):
    _require_conversion(runtime)
    from tests.support import inject_palette_change

    source, target, oracle = (
        tmp_path / name
        for name in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    _native(runtime, source, action="create", timeline="true", tiles="true")
    inject_palette_change(
        source,
        [
            (30, 50, 80, 255),
            (60, 100, 150, 255),
            (90, 130, 170, 255),
            (100, 130, 180, 255),
        ],
        frame_number=2,
    )
    before = _native(runtime, source, action="observe")
    # Assignment must preserve the same linked/Palette/Tileset fixture too.
    code, assigned = _run("assign-color-profile", source, target, {"kind": "none"})
    assert code == 0, assigned
    assert not any(
        item["changed"] for item in assigned["images"] + assigned["palettes"]
    )
    assert not any(
        tile["changed"] for item in assigned["tilesets"] for tile in item["tiles"]
    )
    icc = tmp_path / "linear.icc"
    _linear_icc(icc)
    code, result = _run(
        "convert-color-profile", source, target, {"kind": "icc", "icc_file": str(icc)}
    )
    assert code == 0, result
    expected = _native(
        runtime, source, action="convert", icc=str(icc), output=str(oracle)
    )
    actual = _native(runtime, target, action="observe")
    assert actual == expected
    assert actual["links"] == before["links"] and actual["links"]
    assert len(result["images"]) == len(actual["cels"]) == 4
    assert [item["palette_frame_number"] for item in result["palettes"]] == [1, 2]
    assert all(
        item["changed"] and item["changed_indexes"] == [0, 1, 2, 3]
        for item in result["palettes"]
    )
    assert len(result["tilesets"]) == len(actual["tilesets"]) == 1
    assert len(result["tilesets"][0]["tiles"]) == len(actual["tilesets"][0]) == 2
    # This is a tested 1.3.18.5 behavior: native Convert skips stored Tileset pixels.
    assert actual["tilesets"] == before["tilesets"]
    assert not any(tile["changed"] for tile in result["tilesets"][0]["tiles"])


@pytest.mark.parametrize(
    "command,case,reason",
    [
        (command, case, reason)
        for command in ["assign-color-profile", "convert-color-profile"]
        for case, reason in [
            ("missing", "unreadable"),
            ("directory", "unreadable"),
            ("invalid", "invalid"),
        ]
    ]
    + [
        ("convert-color-profile", "lab", "unsupported_color_space"),
    ],
)
def test_bad_icc_is_typed_and_never_publishes(
    tmp_path: Path, runtime, command: str, case: str, reason: str
):
    from PIL import ImageCms

    if command == "convert-color-profile":
        _require_conversion(runtime)

    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _native(runtime, source, action="create")
    original = source.read_bytes()
    target.write_bytes(b"existing Target")
    icc = tmp_path / "bad.icc"
    if case == "directory":
        icc.mkdir()
    elif case == "invalid":
        icc.write_bytes(b"not a profile")
    elif case == "lab":
        icc.write_bytes(
            ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
        )
    code, result = _run(command, source, target, {"kind": "icc", "icc_file": str(icc)})
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == reason
    assert source.read_bytes() == original and target.read_bytes() == b"existing Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))


def test_convert_plan_matches_standalone_and_step_evidence(tmp_path: Path, runtime):
    _require_conversion(runtime)
    source, target, standalone = (
        tmp_path / name
        for name in ["source.aseprite", "target.aseprite", "standalone.aseprite"]
    )
    _native(runtime, source, action="create")
    icc = tmp_path / "linear.icc"
    _linear_icc(icc)
    profile = {"kind": "icc", "icc_file": str(icc)}
    code, expected = _run("convert-color-profile", source, standalone, profile)
    assert code == 0, expected
    code, result = _plan(
        source,
        target,
        [{"operation": "sprite convert-color-profile", "input": {"profile": profile}}],
    )
    assert code == 0, result
    assert result["steps"][0]["result"] == {
        key: value
        for key, value in expected.items()
        if key not in {"operation", "status", "target_commit"}
    } | {"persisted_reopen_verified": False}
    assert _native(runtime, target, action="observe") == _native(
        runtime, standalone, action="observe"
    )
    original = target.read_bytes()
    icc.write_bytes(b"invalid")
    code, result = _plan(
        source,
        target,
        [
            {
                "operation": "sprite assign-color-profile",
                "input": {"profile": {"kind": "none"}},
            },
            {
                "operation": "sprite convert-color-profile",
                "input": {"profile": profile},
            },
        ],
    )
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["step_number"] == 2
    assert target.read_bytes() == original


def test_conversion_discovery_matches_runtime_and_missing_converter_refuses_publication(
    tmp_path: Path, runtime
):
    manifest_run = spa("schema", "--aseprite", os.environ["SPA_TEST_ASEPRITE"])
    assert manifest_run.returncode == 0, manifest_run.stdout
    manifest = json.loads(manifest_run.stdout)
    available = "aseprite_convert_color_profile" in runtime.verified_capabilities
    operations = {entry["operation"] for entry in manifest["operations"]}
    assert "spa sprite assign-color-profile" in operations
    assert ("spa sprite convert-color-profile" in operations) == available
    if available:
        return
    assert sys.platform == "linux", "expected native Color Profile conversion"
    gap = next(
        item
        for item in manifest["capability_gaps"]
        if item["capability"] == "spa sprite convert-color-profile"
    )
    assert "aseprite_convert_color_profile" in gap["evidence"]
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _native(runtime, source, action="create")
    original = source.read_bytes()
    target.write_bytes(b"existing Target")
    code, result = _run("convert-color-profile", source, target, {"kind": "srgb"})
    assert code != 0 and result["code"] == "runtime_incompatible", result
    assert result["details"]["missing_capabilities"] == [
        "aseprite_convert_color_profile"
    ]
    code, result = _plan(
        source,
        target,
        [
            {
                "operation": "sprite convert-color-profile",
                "input": {"profile": {"kind": "srgb"}},
            }
        ],
    )
    assert code != 0 and result["code"] == "runtime_incompatible", result
    assert result["details"]["missing_capabilities"] == [
        "aseprite_convert_color_profile"
    ]
    assert source.read_bytes() == original and target.read_bytes() == b"existing Target"
    assert not list(tmp_path.glob(".*.staged.aseprite"))
