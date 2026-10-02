"""Public Palette operations against native Frame-based Palette Changes."""

from pathlib import Path

import pytest

from tests.palette.support import palette_fixture as _fixture
from tests.palette.support import run_palette as _run

pytestmark = pytest.mark.e2e


def test_list_and_get_distinguish_requested_frame_from_owning_change(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, runtime)
    original = source.read_bytes()
    code, listed = _run("palette", "list", sprite_file=str(source))
    assert code == 0, listed
    assert listed["frame_count"] == 5
    changes = listed["palette_changes"]
    assert [
        (change["palette_frame_number"], change["effective_frame_range"])
        for change in changes
    ] == [
        (1, {"from_frame": 1, "to_frame": 2}),
        (3, {"from_frame": 3, "to_frame": 4}),
        (5, {"from_frame": 5, "to_frame": 5}),
    ]
    assert [change["entries"][1]["color"]["red"] for change in changes] == [
        240,
        40,
        220,
    ]
    for requested, owner in [(5, 5), (1, 1), (2, 1), (3, 3), (4, 3)]:
        code, got = _run(
            "palette", "get", sprite_file=str(source), frame_number=requested
        )
        assert code == 0, got
        assert got["frame_number"] == requested
        assert got["palette"] == next(
            change for change in changes if change["palette_frame_number"] == owner
        )
    assert source.read_bytes() == original


@pytest.mark.parametrize(
    "frame_number",
    [6, 2**53 + 1, 2**63, 10**400],
    ids=[
        "past-last-frame",
        "beyond-exact-double",
        "beyond-signed-64",
        "beyond-double-range",
    ],
)
def test_get_rejects_a_frame_outside_the_timeline(
    tmp_path: Path, runtime, frame_number: int
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, runtime)
    code, result = _run(
        "palette", "get", sprite_file=str(source), frame_number=frame_number
    )
    assert code != 0 and result["code"] == "palette_frame_out_of_bounds", result
    assert result["details"]["frame_number"] == frame_number
    assert result["details"]["frame_count"] == 5


@pytest.mark.parametrize("mode", ["rgb", "grayscale", "indexed"])
def test_set_edits_only_the_exact_change_and_rereads_persisted_entries(
    tmp_path: Path, runtime, mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, runtime, mode)
    original = source.read_bytes()
    code, before = _run("palette", "list", sprite_file=str(source))
    assert code == 0, before
    code, cels_before = _run(
        "cel",
        "list",
        sprite_file=str(source),
        layer={"layer_path": [1]},
        from_frame=1,
        to_frame=5,
    )
    assert code == 0, cels_before
    image_source = {
        "kind": "individual",
        "target": {"layer": {"layer_path": [1]}, "frame_number": 3},
        "rectangle": {"x": 0, "y": 0, "width": 3, "height": 1},
    }
    code, pixels_before = _run(
        "image", "get", sprite_file=str(source), source=image_source
    )
    assert code == 0, pixels_before
    entries = [
        {"index": 1, "color": {"red": 120, "green": 180, "blue": 40, "alpha": 77}},
        {"index": 2, "color": {"red": 5, "green": 10, "blue": 15, "alpha": 42}},
    ]
    code, edited = _run(
        "palette",
        "set",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=False,
        palette_frame_number=3,
        entries=entries,
    )
    assert code == 0, edited
    assert edited["persisted_reopen_verified"] is True
    assert edited["palette"]["palette_frame_number"] == 3
    assert edited["palette"]["effective_frame_range"] == {
        "from_frame": 3,
        "to_frame": 4,
    }
    assert edited["palette"]["entries"][1:3] == entries
    expected = before["palette_changes"]
    expected[1]["entries"][1:3] = entries
    assert edited["palette_changes"] == expected
    code, reread = _run("palette", "list", sprite_file=str(target))
    assert code == 0 and reread["palette_changes"] == expected, reread
    code, effective = _run("palette", "get", sprite_file=str(target), frame_number=4)
    assert code == 0 and effective["palette"] == edited["palette"], effective
    code, cels_after = _run(
        "cel",
        "list",
        sprite_file=str(target),
        layer={"layer_path": [1]},
        from_frame=1,
        to_frame=5,
    )
    assert code == 0 and cels_after["cels"] == cels_before["cels"], cels_after
    code, pixels_after = _run(
        "image", "get", sprite_file=str(target), source=image_source
    )
    assert code == 0 and pixels_after["snapshot"] == pixels_before["snapshot"], (
        pixels_after
    )
    assert source.read_bytes() == original


def test_info_publishes_entry_edit_capability_and_explains_lifecycle_gaps() -> None:
    code, result = _run("info")
    assert code == 0, result
    assert "aseprite_palette_entries" in result["runtime"]["verified_capabilities"]
    for command in ("spa palette list", "spa palette get", "spa palette set"):
        assert command in result["supported_capabilities"]
    for command in ("spa palette add", "spa palette remove"):
        assert command not in result["supported_capabilities"]
        gap = next(
            gap for gap in result["capability_gaps"] if gap["capability"] == command
        )
        assert "public" in gap["evidence"]
        assert "save/close/reopen" in gap["evidence"]


@pytest.mark.parametrize(
    ("change_frame", "index", "failure"),
    [
        (2, 1, "palette_change_missing"),
        (6, 1, "palette_change_missing"),
        (3, 4, "palette_index_out_of_bounds"),
        (2**53 + 1, 1, "palette_change_missing"),
        (2**63, 1, "palette_change_missing"),
        (3, 2**53 + 1, "palette_index_out_of_bounds"),
        (3, 10**400, "palette_index_out_of_bounds"),
    ],
)
def test_set_validates_every_address_before_publication(
    tmp_path: Path, runtime, change_frame: int, index: int, failure: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(original)
    code, result = _run(
        "palette",
        "set",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=change_frame,
        entries=[
            {"index": 0, "color": {"red": 9, "green": 8, "blue": 7, "alpha": 255}},
            {"index": index, "color": {"red": 6, "green": 5, "blue": 4, "alpha": 255}},
        ],
    )
    assert code != 0 and result["code"] == failure, result
    assert result["details"]["palette_frame_number"] == change_frame
    if failure == "palette_index_out_of_bounds":
        assert result["details"]["index"] == index
    assert source.read_bytes() == original and target.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


@pytest.mark.parametrize(
    "change_frame,red,green,blue",
    [(1, 40, 80, 220), (3, 240, 40, 60), (3, 220, 100, 30)],
)
def test_set_refuses_native_save_that_eliminates_a_palette_change(
    tmp_path: Path, runtime, change_frame: int, red: int, green: int, blue: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, runtime)
    original = source.read_bytes()
    target.write_bytes(original)
    code, result = _run(
        "palette",
        "set",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=change_frame,
        entries=[
            {
                "index": 1,
                "color": {"red": red, "green": green, "blue": blue, "alpha": 255},
            }
        ],
    )
    assert code != 0 and result["code"] == "kernel_execution_failed", result
    assert "palette" in result["details"]["reason"].lower()
    assert source.read_bytes() == original and target.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "source.aseprite",
        "target.aseprite",
    ]


def test_set_supports_explicit_in_place_and_same_value_edits(
    tmp_path: Path, runtime
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, runtime)
    code, before = _run("palette", "list", sprite_file=str(source))
    assert code == 0, before
    code, result = _run(
        "palette",
        "set",
        source_sprite_file=str(source),
        target_sprite_file=str(source),
        in_place=True,
        overwrite=True,
        palette_frame_number=3,
        entries=[before["palette_changes"][1]["entries"][1]],
    )
    assert code == 0 and result["palette_changes"] == before["palette_changes"], result
    assert result["target_commit"]["target_sprite_file"] == str(source)


@pytest.mark.parametrize("red", [240, 200])
def test_set_preserves_global_transparent_index_even_with_a_short_palette(
    tmp_path: Path, runtime, red: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source, runtime, short_palette=True)
    original = source.read_bytes()
    target.write_bytes(original)
    code, result = _run(
        "palette",
        "set",
        source_sprite_file=str(source),
        target_sprite_file=str(target),
        in_place=False,
        overwrite=True,
        palette_frame_number=1,
        entries=[
            {"index": 1, "color": {"red": red, "green": 40, "blue": 60, "alpha": 255}}
        ],
    )
    if red == 240:
        assert code == 0, result
        code, inspected = _run(
            "sprite", "get", sprite_file=str(target), inspection_scope=["palettes"]
        )
        assert code == 0 and inspected["metadata"]["transparent_color_index"] == 3, (
            inspected
        )
    else:
        assert code != 0 and result["code"] == "kernel_execution_failed", result
        assert "transparent_color_index" in result["details"]["reason"]
        assert target.read_bytes() == original
    assert source.read_bytes() == original
