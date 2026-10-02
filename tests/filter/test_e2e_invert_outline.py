"""Standalone filters compared with independent native command invocations."""

import pytest

from tests.filter.support import native_script, observe_images, run

pytestmark = pytest.mark.e2e


def request(mode, names, **extra):
    result = {
        "color_mode": mode,
        "channels": {"kind": "components", "names": names},
        "cels_target": {
            "kind": "selected",
            "layers": [{"layer_path": [1]}],
            "frame_numbers": [1],
        },
    }
    if mode == "indexed":
        result["palette_frame_number"] = 1
    return {**result, **extra}


def invoke(operation, source, target, **parameters):
    return run(
        "filter",
        operation,
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=parameters.pop("overwrite", False),
        **parameters,
    )


def test_rgb_invert_tracer(tmp_path, runtime):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode="rgb")
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation="invert-color",
        channels=1,
    )
    code, result = invoke("invert-color", source, target, **request("rgb", ["red"]))
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)
    assert result["persisted_reopen_verified"] is True
    cel = observe_images(runtime, target)["cels"][0]
    center = cel["pixels"][(2 - cel["y"]) * cel["width"] + 2 - cel["x"]]
    assert center == (224 | 79 << 8 | 137 << 16 | 143 << 24)


CHANNELS = [
    (mode, [name], flag)
    for mode, values in [
        ("rgb", [("red", 1), ("green", 2), ("blue", 4), ("alpha", 8)]),
        ("grayscale", [("gray", 16), ("alpha", 8)]),
        ("indexed", [("red", 1), ("green", 2), ("blue", 4), ("alpha", 8)]),
    ]
    for name, flag in values
] + [
    ("rgb", ["red", "alpha"], 9),
    ("grayscale", ["gray", "alpha"], 24),
    ("indexed", ["red", "alpha"], 9),
]


@pytest.mark.parametrize("mode,names,flags", CHANNELS)
def test_invert_channels_native_parity(tmp_path, runtime, mode, names, flags):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode=mode)
    before = source.read_bytes()
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation="invert-color",
        channels=flags,
    )
    code, result = invoke("invert-color", source, target, **request(mode, names))
    assert code == 0, result
    assert result["channels"] == {"kind": "components", "names": names}
    assert result["persisted_reopen_verified"] is True
    assert observe_images(runtime, target) == observe_images(runtime, oracle)
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "mode,names",
    [
        ("rgb", ["red", "green", "blue", "alpha"]),
        ("grayscale", ["gray", "alpha"]),
        ("indexed", None),
    ],
)
def test_invert_two_pass_valid_paths_restore_pixels(tmp_path, runtime, mode, names):
    source, first, second = (
        tmp_path / n for n in ["source.aseprite", "first.aseprite", "second.aseprite"]
    )
    native_script(
        runtime, "invert_outline_source.lua", source=source, mode=mode, opaque="true"
    )
    parameters = request(mode, names or ["red"])
    if names is None:
        parameters["channels"] = {"kind": "index"}
    for before, after in [(source, first), (first, second)]:
        code, result = invoke("invert-color", before, after, **parameters)
        assert code == 0, result
        assert result["persisted_reopen_verified"] is True
    assert observe_images(runtime, source) == observe_images(runtime, second)


def colors(mode):
    if mode == "indexed":
        return {"kind": "palette-index", "index": 126}, {
            "kind": "palette-index",
            "index": 129,
        }
    if mode == "grayscale":
        return {"kind": "grayscale", "gray": 211, "alpha": 203}, {
            "kind": "grayscale",
            "gray": 19,
            "alpha": 255,
        }
    return {"kind": "rgba", "red": 211, "green": 157, "blue": 89, "alpha": 203}, {
        "kind": "rgba",
        "red": 19,
        "green": 23,
        "blue": 29,
        "alpha": 255,
    }


def outline_request(mode="rgb", names=None, **extra):
    outline, background = colors(mode)
    result = request(
        mode,
        names
        or (
            ["gray", "alpha"]
            if mode == "grayscale"
            else ["red", "green", "blue", "alpha"]
        ),
    )
    if mode == "indexed":
        result["channels"] = {"kind": "index"}
    return {
        **result,
        "outline_color": outline,
        "background_color": background,
        "place": "outside",
        "tiled_mode": "none",
        "matrix": {"kind": "preset", "name": "circle"},
        **extra,
    }


# Raw numeric constants belong only to the independent oracle.
MATRICES = [
    ("none", 0),
    ("circle", 170),
    ("square", 495),
    ("horizontal", 40),
    ("vertical", 130),
]


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("place,native_place", [("outside", 0), ("inside", 1)])
@pytest.mark.parametrize("name,native_matrix", MATRICES)
def test_outline_every_preset_and_place_native_parity(
    tmp_path, runtime, mode, place, native_place, name, native_matrix
):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode=mode)
    original = source.read_bytes()
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation="outline",
        channels={"rgb": 15, "grayscale": 24, "indexed": 32}[mode],
        place=native_place,
        matrix=native_matrix,
        tiled=0,
    )
    parameters = outline_request(
        mode, place=place, matrix={"kind": "preset", "name": name}
    )
    code, result = invoke("outline", source, target, **parameters)
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)
    for field in [
        "place",
        "matrix",
        "tiled_mode",
        "outline_color",
        "background_color",
        "channels",
    ]:
        assert result[field] == parameters[field]
    assert result["persisted_reopen_verified"] is True
    if name == "none":
        assert result["changed"] is False
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "tiled,native_tiled", [("none", 0), ("x", 1), ("y", 2), ("both", 3)]
)
@pytest.mark.parametrize("place,native_place", [("outside", 0), ("inside", 1)])
def test_outline_asymmetric_custom_and_tiled_edges(
    tmp_path, runtime, tiled, native_tiled, place, native_place
):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode="rgb")
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation="outline",
        channels=15,
        place=native_place,
        matrix=65,
        tiled=native_tiled,
    )
    code, result = invoke(
        "outline",
        source,
        target,
        **outline_request(
            place=place,
            tiled_mode=tiled,
            matrix={"kind": "custom", "neighbors": ["top-left", "bottom-left"]},
        ),
    )
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)


@pytest.mark.parametrize(
    "mode,names,flags", [case for case in CHANNELS if case[0] != "indexed"]
)
def test_outline_component_projection_native_parity(
    tmp_path, runtime, mode, names, flags
):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode=mode)
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation="outline",
        channels=flags,
        place=0,
        matrix=170,
        tiled=0,
    )
    code, result = invoke("outline", source, target, **outline_request(mode, names))
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)


@pytest.mark.parametrize("operation", ["invert-color", "outline"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_selection_limits_native_mutation(tmp_path, runtime, operation, mode):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_source.lua", source=source, mode=mode)
    parameters = (
        outline_request(mode)
        if operation == "outline"
        else request(mode, ["gray"] if mode == "grayscale" else ["red"])
    )
    flags = (
        {"rgb": 15, "grayscale": 24, "indexed": 32}[mode]
        if operation == "outline"
        else (16 if mode == "grayscale" else 1)
    )
    parameters["selection"] = {
        "kind": "all",
        "rectangle": {"x": 2, "y": 2, "width": 1, "height": 1},
    }
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation=operation,
        channels=flags,
        place=0,
        matrix=170,
        tiled=0,
        selection="center",
    )
    code, result = invoke(operation, source, target, **parameters)
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)


@pytest.mark.parametrize("size", [128, 255, 256])
def test_index_palette_bounds_and_selection_excludes_unsafe_pixels(
    tmp_path, runtime, size
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "invert_outline_source.lua",
        source=source,
        mode="indexed",
        palette_size=size,
        unsafe="true",
    )
    before = source.read_bytes()
    parameters = request("indexed", ["red"], channels={"kind": "index"})
    code, result = invoke("invert-color", source, target, **parameters)
    if size == 256:
        assert code == 0, result
    else:
        assert code != 0 and result["code"] == "filter_index_out_of_bounds", result
        violations = result["details"]["index_violations"]
        assert result["details"]["palette_basis"]
        assert all(
            {
                "source_index",
                "result_index",
                "layer_path",
                "frame_number",
                "canvas_position",
            }
            <= violation.keys()
            for violation in violations
        )
        assert any(
            v["source_index"] == 255
            and v["result_index"] == 0
            and v["canvas_position"] == {"x": 4, "y": 4}
            for v in violations
        )
        assert not target.exists()
    assert source.read_bytes() == before
    # The selected safe source 127 maps to 128; palette size 128 must refuse that result.
    parameters["selection"] = {
        "kind": "all",
        "rectangle": {"x": 2, "y": 2, "width": 1, "height": 1},
    }
    code, result = invoke(
        "invert-color", source, tmp_path / "selected.aseprite", **parameters
    )
    assert (code == 0) == (size >= 129), result


@pytest.mark.parametrize("operation", ["invert-color", "outline"])
@pytest.mark.parametrize("target_kind", ["all", "mixed", "tilemap"])
def test_resolved_tilemaps_refuse_whole_operation(
    tmp_path, runtime, operation, target_kind
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    before = source.read_bytes()
    target.write_bytes(b"retained target")
    parameters = (
        outline_request() if operation == "outline" else request("rgb", ["red"])
    )
    parameters["cels_target"] = (
        {"kind": "all"}
        if target_kind == "all"
        else {
            "kind": "selected",
            "layers": [
                {"layer_path": [i]} for i in ([1, 2] if target_kind == "mixed" else [2])
            ],
            "frame_numbers": [1],
        }
    )
    code, result = invoke(operation, source, target, overwrite=True, **parameters)
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert source.read_bytes() == before and target.read_bytes() == b"retained target"


@pytest.mark.parametrize("operation", ["invert-color", "outline"])
def test_unrelated_tilemaps_preserved(tmp_path, runtime, operation):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "tilemap.lua", source=source, mode="rgb")
    before = observe_images(runtime, source)
    parameters = (
        outline_request() if operation == "outline" else request("rgb", ["red"])
    )
    code, result = invoke(operation, source, target, **parameters)
    assert code == 0, result
    after = observe_images(runtime, target)
    assert after["tiles"] == before["tiles"]
    assert [cel for cel in after["cels"] if cel["layer"] == "Tilemap"] == [
        cel for cel in before["cels"] if cel["layer"] == "Tilemap"
    ]


def test_indexed_outline_components_gap_before_mutation(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(runtime, "invert_outline_source.lua", source=source, mode="indexed")
    before = source.read_bytes()
    code, result = invoke(
        "outline",
        source,
        target,
        **outline_request(
            "indexed", channels={"kind": "components", "names": ["red", "alpha"]}
        ),
    )
    assert code != 0 and result["code"] == "filter_unsupported_document", result
    assert source.read_bytes() == before and not target.exists()


@pytest.mark.parametrize("operation", ["invert-color", "outline"])
@pytest.mark.parametrize("background", [False, True])
def test_background_and_links_preserve_native_effects(
    tmp_path, runtime, operation, background
):
    source, target, oracle = (
        tmp_path / n for n in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(
        runtime,
        "invert_outline_source.lua",
        source=source,
        mode="rgb",
        background=str(background).lower(),
        linked="true",
    )
    native_script(
        runtime,
        "invert_outline_native.lua",
        source=source,
        target=oracle,
        operation=operation,
        channels=7,
        place=0,
        matrix=170,
        tiled=0,
    )
    parameters = (
        outline_request(names=["red", "green", "blue"])
        if operation == "outline"
        else request("rgb", ["red", "green", "blue"])
    )
    code, result = invoke(operation, source, target, **parameters)
    assert code == 0, result
    assert observe_images(runtime, target) == observe_images(runtime, oracle)
    assert {cel["frame_number"] for cel in result["cel_effects"]} == {1, 2}


def test_index_padding_participates_in_palette_safety(tmp_path, runtime):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "invert_outline_source.lua",
        source=source,
        mode="indexed",
        palette_size=255,
        trimmed="true",
    )
    before = source.read_bytes()
    parameters = request("indexed", ["red"], channels={"kind": "index"})
    code, result = invoke("invert-color", source, target, **parameters)
    assert code != 0 and result["code"] == "filter_index_out_of_bounds", result
    assert any(
        v["source_index"] == 0
        and v["result_index"] == 255
        and v["canvas_position"] == {"x": 0, "y": 0}
        for v in result["details"]["index_violations"]
    )
    assert not target.exists() and source.read_bytes() == before
    parameters["selection"] = {
        "kind": "all",
        "rectangle": {"x": 2, "y": 2, "width": 1, "height": 1},
    }
    code, result = invoke("invert-color", source, target, **parameters)
    assert code == 0, result
    assert observe_images(runtime, target)["cels"][0]["pixels"] == [128]


@pytest.mark.parametrize(
    "matrix,expected_offsets",
    [
        ({"kind": "preset", "name": "circle"}, {(0, -1), (-1, 0), (1, 0), (0, 1)}),
        (
            {"kind": "preset", "name": "square"},
            {(x, y) for x in [-1, 0, 1] for y in [-1, 0, 1] if (x, y) != (0, 0)},
        ),
        ({"kind": "preset", "name": "horizontal"}, {(-1, 0), (1, 0)}),
        ({"kind": "preset", "name": "vertical"}, {(0, -1), (0, 1)}),
        ({"kind": "custom", "neighbors": ["top-left"]}, {(1, 1)}),
    ],
)
def test_outline_discriminating_point_witness(
    tmp_path, runtime, matrix, expected_offsets
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "invert_outline_source.lua",
        source=source,
        mode="rgb",
        point_only="true",
    )
    code, result = invoke("outline", source, target, **outline_request(matrix=matrix))
    assert code == 0, result
    cel = observe_images(runtime, target)["cels"][0]
    outline = 211 | 157 << 8 | 89 << 16 | 203 << 24
    coordinates = {
        (cel["x"] + i % cel["width"] - 2, cel["y"] + i // cel["width"] - 2)
        for i, pixel in enumerate(cel["pixels"])
        if pixel == outline
    }
    assert coordinates == expected_offsets


@pytest.mark.parametrize("operation", ["invert-color", "outline"])
@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
@pytest.mark.parametrize("width", [5, 8])
def test_explicit_empty_selection_preserves_every_image(
    tmp_path, runtime, operation, mode, width
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime, "invert_outline_source.lua", source=source, mode=mode, width=width
    )
    before = observe_images(runtime, source)
    parameters = (
        outline_request(mode)
        if operation == "outline"
        else request(mode, ["gray"] if mode == "grayscale" else ["red"])
    )
    parameters["selection"] = {"kind": "empty"}
    code, result = invoke(operation, source, target, **parameters)
    assert code == 0, result
    assert result["changed"] is False
    assert result["persisted_reopen_verified"] is True
    assert observe_images(runtime, target) == before


def test_tiled_axes_have_discriminating_corner_witnesses(tmp_path, runtime):
    source = tmp_path / "source.aseprite"
    native_script(runtime, "invert_outline_source.lua", source=source, mode="rgb")
    observations = []
    for tiled in ["none", "x", "y", "both"]:
        target = tmp_path / f"{tiled}.aseprite"
        code, result = invoke(
            "outline",
            source,
            target,
            **outline_request(
                tiled_mode=tiled,
                matrix={"kind": "custom", "neighbors": ["top-left", "bottom-left"]},
            ),
        )
        assert code == 0, result
        observations.append(observe_images(runtime, target)["cels"])
    assert all(
        first != second
        for i, first in enumerate(observations)
        for second in observations[i + 1 :]
    )


@pytest.mark.parametrize("layer_numbers", [[1, 2], [2, 1]])
def test_mixed_background_outline_uses_ordinary_color_anchor(
    tmp_path, runtime, layer_numbers
):
    source, target, oracle = (
        tmp_path / name
        for name in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(runtime, "invert_outline_mixed.lua", action="source", source=source)
    native_script(
        runtime,
        "invert_outline_mixed.lua",
        action="native",
        source=source,
        target=oracle,
    )
    parameters = outline_request(names=["red", "green", "blue"], place="inside")
    parameters["background_color"]["alpha"] = 0
    parameters["cels_target"]["layers"] = [
        {"layer_path": [number]} for number in layer_numbers
    ]
    code, result = invoke("outline", source, target, **parameters)
    assert code == 0, result
    observed = observe_images(runtime, target)
    assert observed == observe_images(runtime, oracle)
    ordinary = next(cel for cel in observed["cels"] if cel["layer"] == "Ordinary")
    assert ordinary["pixels"] == [211 | 157 << 8 | 89 << 16 | 255 << 24]


def test_background_only_outline_retains_native_opaque_color_projection(
    tmp_path, runtime
):
    source, target, oracle = (
        tmp_path / name
        for name in ["source.aseprite", "target.aseprite", "oracle.aseprite"]
    )
    native_script(
        runtime, "invert_outline_mixed.lua", action="source", source=source, only="true"
    )
    native_script(
        runtime,
        "invert_outline_mixed.lua",
        action="native",
        source=source,
        target=oracle,
    )
    parameters = outline_request(names=["red", "green", "blue"], place="inside")
    parameters["background_color"]["alpha"] = 0
    code, result = invoke("outline", source, target, **parameters)
    assert code == 0, result
    observed = observe_images(runtime, target)
    assert observed == observe_images(runtime, oracle)
    assert observed["cels"][0]["pixels"][12] == 211 | 157 << 8 | 89 << 16 | 255 << 24


@pytest.mark.parametrize("field", ["outline_color", "background_color"])
def test_outline_invalid_palette_color_preserves_source_and_existing_target(
    tmp_path, runtime, field
):
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    native_script(
        runtime,
        "invert_outline_source.lua",
        source=source,
        mode="indexed",
        palette_size=130,
    )
    original = source.read_bytes()
    target.write_bytes(b"preserved destination")
    parameters = outline_request("indexed")
    parameters[field] = {"kind": "palette-index", "index": 130}
    code, result = invoke("outline", source, target, overwrite=True, **parameters)
    assert code != 0, result
    assert result["code"] == "filter_invalid_target", result
    assert source.read_bytes() == original
    assert target.read_bytes() == b"preserved destination"
