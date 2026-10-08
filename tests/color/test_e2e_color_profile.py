"""Color Profile commands preserve or transform native stored color facts."""

import json
import os
import struct
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

import pytest

from spa.adapters.aseprite.aseprite import probe
from spa.adapters.aseprite.invocation import prepare_invocation
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.public import RuntimeRequest
from tests.support import icc_fixture_path, process_diagnostics, spa

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


def _native(
    runtime, source: Path, *, fixture: str = "profile_sprite.lua", **params: str
) -> dict:
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
                str(Path(__file__).parent / "fixtures" / fixture),
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
    # The supported file is fixed. Native calls independently establish its result.
    data = files("spa.kernel").joinpath("color/profiles/linear_srgb.icc").read_bytes()
    path.write_bytes(data)
    return data


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
    actual = _native(runtime, converted, action="observe")
    assert actual == _native(
        runtime, assigned, action="convert", output=str(tmp_path / "oracle.aseprite")
    )
    assert result["images"][0]["changed"] == (mode != "indexed")
    assert result["palettes"][0]["changed"] == (mode != "grayscale")
    code, planned = _plan(
        assigned,
        tmp_path / "plan.aseprite",
        [
            {
                "operation": "sprite convert-color-profile",
                "input": {"profile": {"kind": "srgb"}},
            }
        ],
    )
    assert code == 0, planned
    assert _native(runtime, tmp_path / "plan.aseprite", action="observe") == actual
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


def test_convert_refuses_lab_source_and_live_plan_profile_before_publication(
    tmp_path: Path, runtime
):
    from PIL import ImageCms

    _require_conversion(runtime)
    source, lab_source, target = (
        tmp_path / name
        for name in ["source.aseprite", "lab.aseprite", "target.aseprite"]
    )
    _native(runtime, source, action="create")
    icc = tmp_path / "lab.icc"
    icc.write_bytes(ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes())
    lab = {"kind": "icc", "icc_file": str(icc)}
    code, assigned = _run("assign-color-profile", source, lab_source, lab)
    assert code == 0, assigned
    original = lab_source.read_bytes()
    target.write_bytes(b"existing Target")
    code, result = _run("convert-color-profile", lab_source, target, {"kind": "srgb"})
    assert code != 0 and result["code"] == "color_profile_source_unsupported", result
    assert result["details"]["icc_color_space"] == "Lab"
    assert result["details"]["step_number"] is None
    convert = {
        "operation": "sprite convert-color-profile",
        "input": {"profile": {"kind": "srgb"}},
    }
    assign = {"operation": "sprite assign-color-profile", "input": {"profile": lab}}
    for plan_source, steps in [(lab_source, [convert]), (source, [assign, convert])]:
        code, result = _plan(plan_source, target, steps)
        assert code != 0 and result["code"] == "color_profile_source_unsupported", (
            result
        )
        assert result["details"]["icc_color_space"] == "Lab"
        assert result["details"]["step_number"] == len(steps)
        assert (
            lab_source.read_bytes() == original
            and target.read_bytes() == b"existing Target"
        )
        assert not list(tmp_path.glob(".*.staged.aseprite"))
    # A later explicit Assign replaces the live source interpretation for Convert.
    _linear_icc(icc)
    code, result = _plan(lab_source, target, [assign, convert])
    assert code == 0, result
    assert result["steps"][1]["result"]["images"][0]["changed"] is True


@pytest.mark.parametrize("case", ["srgb", "metadata", "lut", "curve"])
@pytest.mark.parametrize("in_place", [False, True])
def test_convert_refuses_unlisted_icc_file_but_assign_preserves_it(
    tmp_path: Path, runtime, case: str, in_place: bool
):
    from PIL import ImageCms

    _require_conversion(runtime)
    source, assigned, target = (
        tmp_path / name
        for name in ["source.aseprite", "assigned.aseprite", "target.aseprite"]
    )
    _native(runtime, source, action="create")
    icc = tmp_path / "unlisted.icc"
    raw = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    if case == "metadata":
        raw = bytearray(
            files("spa.kernel")
            .joinpath("color/profiles/display_p3_cc0.icc")
            .read_bytes()
        )
        raw[35] = (
            1  # Only the creation second changes; this is a different file identity.
        )
    elif case == "lut":
        raw = bytearray((Path(__file__).parent / "fixtures/rgb_lut.icc").read_bytes())
    elif case == "curve":
        for index in range(struct.unpack_from(">I", raw, 128)[0]):
            tag, offset, size = struct.unpack_from(">4sII", raw, 132 + 12 * index)
            if tag in {b"rTRC", b"gTRC", b"bTRC"}:
                assert size == 32
                raw[offset : offset + size] = struct.pack(
                    ">4sIHH5i", b"para", 0, 3, 0, 131072, 65536, 0, 16384, 32768
                )
    icc.write_bytes(raw)
    ImageCms.ImageCmsProfile(str(icc))  # All are valid file inputs for Assign.
    profile = {"kind": "icc", "icc_file": str(icc)}
    target.write_bytes(b"existing Target")
    original = source.read_bytes()
    conversion_target = source if in_place else target
    code, result = _run("convert-color-profile", source, conversion_target, profile)
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == "unsupported_profile"
    assert target.read_bytes() == b"existing Target" and source.read_bytes() == original
    code, result = _plan(
        source,
        conversion_target,
        [{"operation": "sprite convert-color-profile", "input": {"profile": profile}}],
    )
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == "unsupported_profile"
    assert result["details"]["step_number"] == 1

    code, result = _run("assign-color-profile", source, assigned, profile)
    assert code == 0, result
    assert not any(item["changed"] for item in result["images"] + result["palettes"])
    assigned_bytes = assigned.read_bytes()
    code, result = _run(
        "convert-color-profile",
        assigned,
        assigned if in_place else target,
        {"kind": "srgb"},
    )
    assert code != 0 and result["code"] == "color_profile_source_unsupported", result
    assert (
        target.read_bytes() == b"existing Target"
        and assigned.read_bytes() == assigned_bytes
    )
    convert = {
        "operation": "sprite convert-color-profile",
        "input": {"profile": {"kind": "srgb"}},
    }
    assign = {"operation": "sprite assign-color-profile", "input": {"profile": profile}}
    for plan_source, steps in [(assigned, [convert]), (source, [assign, convert])]:
        code, result = _plan(plan_source, plan_source if in_place else target, steps)
        assert code != 0 and result["code"] == "color_profile_source_unsupported", (
            result
        )
        assert result["details"]["step_number"] == len(steps)
        assert (
            source.read_bytes() == original and assigned.read_bytes() == assigned_bytes
        )
        assert target.read_bytes() == b"existing Target"
        assert not list(tmp_path.glob(".*.staged.aseprite"))


@pytest.mark.parametrize("profile_source", ["redistributable", "caller_apple"])
def test_p3_to_srgb_preserves_preparation_and_plan_parity(
    tmp_path: Path, runtime, profile_source: str
):
    import hashlib

    _require_conversion(runtime)
    source, assigned, target, planned, oracle = (
        tmp_path / name
        for name in [
            "source.aseprite",
            "p3.aseprite",
            "target.aseprite",
            "plan.aseprite",
            "oracle.aseprite",
        ]
    )
    before = _native(runtime, source, action="create", p3_sample="true")
    original = source.read_bytes()
    icc = tmp_path / "display-p3.icc"
    if profile_source == "caller_apple":
        icc_input = icc_fixture_path("display_p3")
        expected_sha = (
            "0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0"
        )
    else:
        icc_input = icc_fixture_path("display_p3_cc0")
        expected_sha = (
            "cb51de38e482ee974c0c76b9689e16aad04bad16e226fed2f30c842d15ff3a3d"
        )
    contents = icc_input.read_bytes()
    assert hashlib.sha256(contents).hexdigest() == expected_sha
    icc.write_bytes(contents)
    p3 = {"kind": "icc", "icc_file": str(icc)}
    assert _run("assign-color-profile", source, assigned, p3)[0] == 0
    assigned_bytes = assigned.read_bytes()
    assert contents in assigned_bytes
    code, result = _run("convert-color-profile", assigned, target, {"kind": "srgb"})
    assert code == 0 and result["persisted_reopen_verified"], result
    actual = _native(runtime, target, action="observe")
    expected = _native(runtime, assigned, action="convert", output=str(oracle))
    assert actual == expected
    assert actual["pixels"][0] == 195 | (60 << 8) | (2 << 16) | (127 << 24)
    assert [value >> 24 for value in actual["pixels"]] == [
        value >> 24 for value in before["pixels"]
    ]
    assert all(item["changed"] for item in result["images"] + result["palettes"])
    assign = {"operation": "sprite assign-color-profile", "input": {"profile": p3}}
    convert = {
        "operation": "sprite convert-color-profile",
        "input": {"profile": {"kind": "srgb"}},
    }
    for plan_source, steps in [(source, [assign, convert]), (assigned, [convert])]:
        code, plan_result = _plan(plan_source, planned, steps)
        assert code == 0 and plan_result["persisted_reopen_verified"], plan_result
        assert _native(runtime, planned, action="observe") == actual
    assert source.read_bytes() == original and assigned.read_bytes() == assigned_bytes


@pytest.mark.parametrize(
    "source_kind,target_kind",
    [
        ("srgb", "display_p3_cc0"),
        ("linear_srgb", "display_p3_cc0"),
        ("display_p3_cc0", "linear_srgb"),
        ("none", "linear_srgb"),
        ("none", "display_p3_cc0"),
    ],
)
def test_known_icc_membership_does_not_admit_untested_directions(
    tmp_path: Path, runtime, source_kind: str, target_kind: str
):
    _require_conversion(runtime)
    source, assigned, target = (
        tmp_path / name
        for name in ["source.aseprite", "assigned.aseprite", "target.aseprite"]
    )
    _native(runtime, source, action="create")
    profiles = {}
    for kind in ["linear_srgb", "display_p3_cc0"]:
        path = tmp_path / f"{kind}.icc"
        path.write_bytes(
            files("spa.kernel").joinpath(f"color/profiles/{kind}.icc").read_bytes()
        )
        profiles[kind] = {"kind": "icc", "icc_file": str(path)}
    source_profile = profiles.get(source_kind, {"kind": source_kind})
    assert _run("assign-color-profile", source, assigned, source_profile)[0] == 0
    original = assigned.read_bytes()
    target.write_bytes(b"existing Target")
    code, result = _run(
        "convert-color-profile", assigned, target, profiles[target_kind]
    )
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == "unsupported_conversion"
    code, result = _plan(
        assigned,
        target,
        [
            {
                "operation": "sprite convert-color-profile",
                "input": {"profile": profiles[target_kind]},
            }
        ],
    )
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == "unsupported_conversion"
    assert result["details"]["step_number"] == 1
    assert (
        assigned.read_bytes() == original and target.read_bytes() == b"existing Target"
    )


@pytest.mark.parametrize(
    "profile_kind", ["linear_srgb", "display_p3_cc0", "display_p3"]
)
def test_admitted_same_profile_and_content_noops_remain_successful(
    tmp_path: Path, runtime, profile_kind: str
):
    _require_conversion(runtime)
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    _native(runtime, source, action="create", black="true")
    icc = tmp_path / "known.icc"
    icc.write_bytes(icc_fixture_path(profile_kind).read_bytes())
    profile = {"kind": "icc", "icc_file": str(icc)}
    assert _run("assign-color-profile", source, source, profile)[0] == 0
    for command in ["standalone", "plan"]:
        if command == "standalone":
            code, result = _run("convert-color-profile", source, target, profile)
            evidence = result
        else:
            code, result = _plan(
                source,
                target,
                [
                    {
                        "operation": "sprite convert-color-profile",
                        "input": {"profile": profile},
                    }
                ],
            )
            evidence = result["steps"][0]["result"] if code == 0 else result
        assert code == 0, result
        assert not evidence["profile_changed"]
        assert not any(
            item["changed"] for item in evidence["images"] + evidence["palettes"]
        )
    code, result = _run("convert-color-profile", source, target, {"kind": "srgb"})
    assert code == 0 and result["profile_changed"], result
    assert not any(item["changed"] for item in result["images"] + result["palettes"])
    code, planned = _plan(
        source,
        target,
        [
            {
                "operation": "sprite convert-color-profile",
                "input": {"profile": {"kind": "srgb"}},
            }
        ],
    )
    assert code == 0, planned
    evidence = planned["steps"][0]["result"]
    assert evidence["profile_changed"]
    assert not any(
        item["changed"] for item in evidence["images"] + evidence["palettes"]
    )


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


@pytest.mark.parametrize("source_identity", ["apple", "cc0"])
def test_distinct_p3_profiles_do_not_admit_cross_conversion(
    tmp_path: Path, runtime, source_identity: str
):
    _require_conversion(runtime)
    profiles = {
        "apple": {"kind": "icc", "icc_file": str(icc_fixture_path("display_p3"))},
        "cc0": {
            "kind": "icc",
            "icc_file": str(icc_fixture_path("display_p3_cc0")),
        },
    }
    source, assigned, target = [
        tmp_path / name
        for name in ("source.aseprite", "assigned.aseprite", "target.aseprite")
    ]
    _native(runtime, source, action="create", p3_sample="true")
    first = profiles[source_identity]
    second = profiles["cc0" if source_identity == "apple" else "apple"]
    assert _run("assign-color-profile", source, assigned, first)[0] == 0
    before = assigned.read_bytes()
    target.write_bytes(b"existing Target")
    code, result = _run("convert-color-profile", assigned, target, second)
    assert code != 0 and result["code"] == "color_profile_file_failed", result
    assert result["details"]["reason"] == "unsupported_conversion"
    steps = [
        {"operation": "sprite assign-color-profile", "input": {"profile": first}},
        {"operation": "sprite convert-color-profile", "input": {"profile": second}},
    ]
    code, result = _plan(source, target, steps)
    assert code != 0 and result["details"]["reason"] == "unsupported_conversion", result
    assert result["details"]["step_number"] == 2
    assert assigned.read_bytes() == before
    assert target.read_bytes() == b"existing Target"


def test_native_identity_digest_matches_independent_complete_byte_hashes(
    tmp_path: Path, runtime
):
    import hashlib

    payloads = [
        b"",
        b"abc",
        b"a" * 55,
        b"a" * 56,
        b"a" * 63,
        b"a" * 64,
        b"a" * 65,
        bytes(range(256)),
    ]
    inputs = []
    for index, payload in enumerate(payloads):
        path = tmp_path / f"payload-{index}"
        path.write_bytes(payload)
        inputs.append(str(path))
    index = tmp_path / "inputs.json"
    index.write_text(json.dumps(inputs))
    observed = _native(
        runtime,
        index,
        fixture="profile_digest.lua",
        digest=str(files("spa.kernel").joinpath("foundation/digest.lua")),
    )
    assert observed["sha256"] == [
        hashlib.sha256(payload).hexdigest() for payload in payloads
    ]
