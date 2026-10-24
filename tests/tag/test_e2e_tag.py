"""Tag facts and mutation contracts against a real Aseprite Sprite."""

from pathlib import Path

import pytest

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.support import process_diagnostics

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _tags_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the four-Frame Sprite of `tags.lua`, with two Tags named "same"."""
    lua = run_lua(FIXTURES / "tags.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def _mutation(source: Path, destination: Path, **fields: object) -> dict[str, object]:
    """Return a Tag mutation request that writes source to a new destination."""
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        **fields,
    }


def test_list_get_and_duplicate_name_rejection(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _tags_sprite(runtime, source)
    listed = expect_success("tag list", {"sprite_file": str(source)})
    assert [
        (tag["tag_index"], tag["name"], tag["direction"], tag["repeats"])
        for tag in listed["tags"]
    ] == [
        (1, "same", "forward", 0),
        (2, "same", "reverse", 1),
    ]
    got = expect_success(
        "tag get", {"sprite_file": str(source), "target": {"tag_index": 2}}
    )
    assert got["tag"] == listed["tags"][1]
    ambiguous = run(
        "tag get", {"sprite_file": str(source), "target": {"tag_name": "same"}}
    )
    assert ambiguous.returncode != 0
    assert ambiguous.envelope["code"] == "tag_ambiguous"
    missing = run("tag get", {"sprite_file": str(source), "target": {"tag_index": 3}})
    assert missing.returncode != 0 and missing.envelope["code"] == "tag_missing"


@pytest.mark.parametrize(
    "direction", ["forward", "reverse", "ping_pong", "ping_pong_reverse"]
)
@pytest.mark.parametrize("repeats", [0, 1])
def test_add_roundtrips_native_direction_and_repeat(
    runtime: RuntimeObservation, tmp_path: Path, direction: str, repeats: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tags_sprite(runtime, source)
    added = expect_success(
        "tag add",
        _mutation(
            source,
            target,
            name="new",
            from_frame=2,
            to_frame=3,
            direction=direction,
            repeats=repeats,
        ),
    )
    assert added["persisted_reopen_verified"] is True
    assert added["tag"]["name"] == "new"
    assert added["tag"]["direction"] == direction
    assert added["tag"]["repeats"] == repeats
    assert added["tag"]["from_frame"] == 2
    assert added["tag"]["to_frame"] == 3
    assert "playback_frames" not in added and "loop_count" not in added
    reopened = expect_success("tag list", {"sprite_file": str(target)})
    assert reopened["tags"] == added["tags"]
    assert reopened["tags"][added["tag"]["tag_index"] - 1] == added["tag"]


def test_set_range_rereads_current_index_and_remove_exact_target(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    changed = tmp_path / "changed.aseprite"
    removed = tmp_path / "removed.aseprite"
    _tags_sprite(runtime, source)
    set_result = expect_success(
        "tag set",
        _mutation(
            source,
            changed,
            target={"tag_index": 1},
            properties={
                "from_frame": 4,
                "to_frame": 4,
                "direction": "ping_pong_reverse",
                "repeats": 1,
            },
        ),
    )
    assert set_result["tag"]["from_frame"] == 4
    assert set_result["tag"]["tag_index"] == 2
    assert set_result["tag"]["direction"] == "ping_pong_reverse"
    reopened = expect_success("tag list", {"sprite_file": str(changed)})
    assert reopened["tags"] == set_result["tags"]
    ambiguous = run(
        "tag remove", _mutation(changed, removed, target={"tag_name": "same"})
    )
    assert ambiguous.returncode != 0
    assert ambiguous.envelope["code"] == "tag_ambiguous"
    assert not removed.exists()
    result = expect_success(
        "tag remove", _mutation(changed, removed, target={"tag_index": 2})
    )
    assert result["removed_tag"] == set_result["tag"]
    assert len(result["tags"]) == 1
    reopened = expect_success("tag list", {"sprite_file": str(removed)})
    assert reopened["tags"] == result["tags"]


def test_rejects_range_outside_sprite_without_publication(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tags_sprite(runtime, source)
    rejected = run(
        "tag add",
        _mutation(
            source,
            target,
            name="new",
            from_frame=3,
            to_frame=5,
            direction="forward",
            repeats=0,
        ),
    )
    assert rejected.returncode != 0
    assert rejected.envelope["code"] == "tag_range_out_of_bounds"
    assert not target.exists()


def test_unique_name_partial_set_color_and_explicit_in_place(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _tags_sprite(runtime, source)
    changed = expect_success(
        "tag set",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(source),
            "in_place": True,
            "overwrite": True,
            "target": {"tag_index": 2},
            "properties": {
                "name": "unique",
                "from_frame": 2,
                "direction": "ping_pong",
                "repeats": 0,
                "color": {"red": 25, "green": 100, "blue": 200, "alpha": 255},
            },
        },
    )
    assert changed["tag"]["name"] == "unique"
    assert changed["tag"]["from_frame"] == 2
    assert changed["tag"]["to_frame"] == 4
    assert changed["tag"]["direction"] == "ping_pong"
    assert changed["tag"]["repeats"] == 0
    assert changed["tag"]["color"] == {
        "red": 25,
        "green": 100,
        "blue": 200,
        "alpha": 255,
    }
    got = expect_success(
        "tag get", {"sprite_file": str(source), "target": {"tag_name": "unique"}}
    )
    assert got["tag"] == changed["tag"]
    target = tmp_path / "removed.aseprite"
    removed = expect_success(
        "tag remove", _mutation(source, target, target={"tag_name": "unique"})
    )
    assert removed["removed_tag"] == changed["tag"]
    assert [tag["name"] for tag in removed["tags"]] == ["same"]


def test_empty_names_are_preserved_and_addressed_exactly(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    first = tmp_path / "first.aseprite"
    second = tmp_path / "second.aseprite"
    _tags_sprite(runtime, source)
    add = {
        "name": "",
        "from_frame": 1,
        "to_frame": 1,
        "direction": "forward",
        "repeats": 0,
    }
    result = expect_success("tag add", _mutation(source, first, **add))
    assert result["tag"]["name"] == ""
    got = expect_success(
        "tag get", {"sprite_file": str(first), "target": {"tag_name": ""}}
    )
    assert got["tag"] == result["tag"]
    added = expect_success("tag add", _mutation(first, second, **add))
    assert added["tag"]["name"] == ""
    ambiguous = run("tag get", {"sprite_file": str(second), "target": {"tag_name": ""}})
    assert ambiguous.returncode != 0
    assert ambiguous.envelope["code"] == "tag_ambiguous"
