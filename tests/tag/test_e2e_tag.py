"""Tag facts and mutation contracts against a real Aseprite Sprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _run(*command: str, request: dict[str, object]) -> tuple[int, dict]:
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    return result.returncode, json.loads(result.stdout)


def _fixture(target: Path) -> None:
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    with tempfile.TemporaryDirectory(prefix="spa-tag-fixture-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                "--script",
                str(Path(__file__).parent / "fixtures" / "tags.lua"),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, process_diagnostics(run)


def _mutation(source: Path, destination: Path, **fields: object) -> dict[str, object]:
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(destination),
        "in_place": False,
        "overwrite": False,
        **fields,
    }


def test_list_get_and_duplicate_name_rejection(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source)
    code, listed = _run("tag", "list", request={"sprite_file": str(source)})
    assert code == 0
    assert [
        (tag["tag_index"], tag["name"], tag["direction"], tag["repeats"])
        for tag in listed["tags"]
    ] == [
        (1, "same", "forward", 0),
        (2, "same", "reverse", 1),
    ]
    code, got = _run(
        "tag", "get", request={"sprite_file": str(source), "target": {"tag_index": 2}}
    )
    assert code == 0 and got["tag"] == listed["tags"][1]
    code, ambiguous = _run(
        "tag",
        "get",
        request={"sprite_file": str(source), "target": {"tag_name": "same"}},
    )
    assert code != 0 and ambiguous["code"] == "tag_ambiguous"
    code, missing = _run(
        "tag", "get", request={"sprite_file": str(source), "target": {"tag_index": 3}}
    )
    assert code != 0 and missing["code"] == "tag_missing"


@pytest.mark.parametrize(
    "direction", ["forward", "reverse", "ping_pong", "ping_pong_reverse"]
)
@pytest.mark.parametrize("repeats", [0, 1])
def test_add_roundtrips_native_direction_and_repeat(
    tmp_path: Path, direction: str, repeats: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source)
    code, added = _run(
        "tag",
        "add",
        request=_mutation(
            source,
            target,
            name="new",
            from_frame=2,
            to_frame=3,
            direction=direction,
            repeats=repeats,
        ),
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    assert added["tag"]["name"] == "new"
    assert added["tag"]["direction"] == direction
    assert added["tag"]["repeats"] == repeats
    assert added["tag"]["from_frame"] == 2
    assert added["tag"]["to_frame"] == 3
    assert "playback_frames" not in added and "loop_count" not in added
    code, reopened = _run("tag", "list", request={"sprite_file": str(target)})
    assert code == 0 and reopened["tags"] == added["tags"]
    assert reopened["tags"][added["tag"]["tag_index"] - 1] == added["tag"]


def test_set_range_rereads_current_index_and_remove_exact_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    changed = tmp_path / "changed.aseprite"
    removed = tmp_path / "removed.aseprite"
    _fixture(source)
    code, set_result = _run(
        "tag",
        "set",
        request=_mutation(
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
    assert code == 0, set_result
    assert set_result["tag"]["from_frame"] == 4
    assert set_result["tag"]["tag_index"] == 2
    assert set_result["tag"]["direction"] == "ping_pong_reverse"
    code, reopened = _run("tag", "list", request={"sprite_file": str(changed)})
    assert code == 0 and reopened["tags"] == set_result["tags"]
    code, ambiguous = _run(
        "tag",
        "remove",
        request=_mutation(changed, removed, target={"tag_name": "same"}),
    )
    assert code != 0 and ambiguous["code"] == "tag_ambiguous"
    assert not removed.exists()
    code, result = _run(
        "tag", "remove", request=_mutation(changed, removed, target={"tag_index": 2})
    )
    assert code == 0, result
    assert result["removed_tag"] == set_result["tag"]
    assert len(result["tags"]) == 1
    code, reopened = _run("tag", "list", request={"sprite_file": str(removed)})
    assert code == 0 and reopened["tags"] == result["tags"]


def test_rejects_range_outside_sprite_without_publication(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _fixture(source)
    code, rejected = _run(
        "tag",
        "add",
        request=_mutation(
            source,
            target,
            name="new",
            from_frame=3,
            to_frame=5,
            direction="forward",
            repeats=0,
        ),
    )
    assert code != 0 and rejected["code"] == "tag_range_out_of_bounds"
    assert not target.exists()


def test_unique_name_partial_set_color_and_explicit_in_place(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source)
    code, changed = _run(
        "tag",
        "set",
        request={
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
    assert code == 0, changed
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
    code, got = _run(
        "tag",
        "get",
        request={"sprite_file": str(source), "target": {"tag_name": "unique"}},
    )
    assert code == 0 and got["tag"] == changed["tag"]
    target = tmp_path / "removed.aseprite"
    code, removed = _run(
        "tag",
        "remove",
        request=_mutation(source, target, target={"tag_name": "unique"}),
    )
    assert code == 0 and removed["removed_tag"] == changed["tag"]
    assert [tag["name"] for tag in removed["tags"]] == ["same"]


def test_empty_names_are_preserved_and_addressed_exactly(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    first = tmp_path / "first.aseprite"
    second = tmp_path / "second.aseprite"
    _fixture(source)
    add = {
        "name": "",
        "from_frame": 1,
        "to_frame": 1,
        "direction": "forward",
        "repeats": 0,
    }
    code, result = _run("tag", "add", request=_mutation(source, first, **add))
    assert code == 0 and result["tag"]["name"] == ""
    code, got = _run(
        "tag", "get", request={"sprite_file": str(first), "target": {"tag_name": ""}}
    )
    assert code == 0 and got["tag"] == result["tag"]
    code, added = _run("tag", "add", request=_mutation(first, second, **add))
    assert code == 0 and added["tag"]["name"] == ""
    code, ambiguous = _run(
        "tag", "get", request={"sprite_file": str(second), "target": {"tag_name": ""}}
    )
    assert code != 0 and ambiguous["code"] == "tag_ambiguous"
