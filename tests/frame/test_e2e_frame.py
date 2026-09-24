"""Frame operations against a real Aseprite Sprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

pytestmark = pytest.mark.e2e


def _run(*command: str, request: dict[str, object]) -> dict[str, object]:
    payload = {**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}
    result = spa(*command, "--input-json", json.dumps(payload))
    assert result.returncode == 0, result.stdout
    return json.loads(result.stdout)


def _run_fixture(name: str, **params: str) -> None:
    binary = Path(os.environ["SPA_TEST_ASEPRITE"])
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    fixture = Path(__file__).parent / "fixtures" / name
    with tempfile.TemporaryDirectory(prefix="spa-frame-fixture-") as work:
        prepared = prepare_invocation(binary, resource, Path(work))
        arguments = [
            item
            for key, value in params.items()
            for item in ("--script-param", f"{key}={value}")
        ]
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                *arguments,
                "--script",
                str(fixture),
            ],
            text=True,
            capture_output=True,
            check=False,
            env=prepared.environment,
        )
    assert run.returncode == 0, run.stderr


def _tagged_sprite(target: Path) -> None:
    _run_fixture("tagged.lua", out=str(target))


def _native_link_status(target: Path, out: Path) -> bool:
    _run_fixture("inspect_links.lua", source=str(target), out=str(out))
    return json.loads(out.read_text(encoding="utf-8"))["linked"]


def test_add_empty_frame_persists_one_based_position_and_duration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    added = _run(
        "frame",
        "add",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 1,
            "duration_ms": 340,
        },
    )
    assert added["inserted_frame"] == {"frame_number": 1, "duration_ms": 340}
    assert added["persisted_reopen_verified"] is True
    assert added["tag_adjustments"] == []
    assert added["sprite"]["frames"] == [
        {"frame_number": 1, "duration_ms": 340},
        {"frame_number": 2, "duration_ms": 100},
    ]
    assert [cel["frame_number"] for cel in added["sprite"]["cels"]] == [2]
    listed = _run("frame", "list", request={"sprite_file": str(target)})
    assert listed["frames"] == added["sprite"]["frames"]
    got = _run("frame", "get", request={"sprite_file": str(target), "frame_number": 1})
    assert got["frame"] == added["inserted_frame"]


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_frame_uses_declared_cel_mode_and_persists(
    tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / f"{cel_mode}.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {"kind": "transparent"},
            "overwrite": False,
        },
    )
    duplicated = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": cel_mode,
            "duration_ms": 250,
        },
    )
    assert duplicated["inserted_frame"] == {"frame_number": 2, "duration_ms": 250}
    assert duplicated["source_cel_count"] == 1
    assert duplicated["inserted_cel_count"] == 1
    assert duplicated["cel_relationships_verified"] is True
    assert duplicated["persisted_reopen_verified"] is True
    assert _native_link_status(target, tmp_path / "links.json") is (cel_mode == "link")
    assert _run("frame", "list", request={"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100}
    ]


def test_add_background_frame_uses_explicit_color(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    png = tmp_path / "frame.png"
    color = {"kind": "rgba", "red": 17, "green": 34, "blue": 51, "alpha": 255}
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {
                "kind": "background",
                "background_color": {
                    key: value for key, value in color.items() if key != "kind"
                },
            },
            "overwrite": False,
        },
    )
    added = _run(
        "frame",
        "add",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 1,
            "duration_ms": 1,
            "background_color": color,
        },
    )
    assert added["inserted_cel_count"] == 1
    _run(
        "export",
        "image",
        request={
            "source_sprite_file": str(target),
            "destination": {"path": str(png), "if_exists": "fail"},
            "frame_number": 1,
            "color_mode": "preserve",
            "color_profile": "preserve",
            "transparency": "preserve",
        },
    )
    with Image.open(png) as image:
        assert image.convert("RGBA").getpixel((0, 0)) == (17, 34, 51, 255)


def test_add_reports_native_tag_range_adjustment(tmp_path: Path) -> None:
    source = tmp_path / "tagged.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    added = _run(
        "frame",
        "add",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
            "duration_ms": 65535,
        },
    )
    assert added["inserted_frame"] == {"frame_number": 2, "duration_ms": 65535}
    assert added["tag_adjustments"] == [
        {
            "tag_number": 1,
            "name": "walk",
            "before_from_frame": 1,
            "before_to_frame": 2,
            "after_from_frame": 1,
            "after_to_frame": 3,
        }
    ]
    assert added["sprite"]["tags"][0]["to_frame"] == 3


def test_plan_frame_steps_match_standalone_semantics(tmp_path: Path) -> None:
    target = tmp_path / "plan.aseprite"
    result = _run(
        "plan",
        "run",
        request={
            "plan": {
                "target_sprite_file": str(target),
                "steps": [
                    {
                        "operation": "sprite create",
                        "input": {
                            "width": 3,
                            "height": 2,
                            "color_mode": "rgb",
                            "initial_layer": {"kind": "transparent"},
                        },
                    },
                    {
                        "operation": "frame add",
                        "input": {"frame_number": 2, "duration_ms": 340},
                    },
                    {"operation": "frame list", "input": {}},
                    {
                        "operation": "frame duplicate",
                        "input": {"source_frame_number": 1, "cel_mode": "link"},
                    },
                    {"operation": "frame get", "input": {"frame_number": 2}},
                ],
                "postconditions": {"frame_count": 3},
            }
        },
    )
    assert result["persisted_reopen_verified"] is True
    assert result["steps"][1]["result"]["inserted_frame"] == {
        "frame_number": 2,
        "duration_ms": 340,
    }
    assert len(result["steps"][2]["result"]["frames"]) == 2
    assert result["steps"][3]["result"]["inserted_frame"] == {
        "frame_number": 2,
        "duration_ms": 100,
    }
    assert result["steps"][4]["result"]["frame"]["duration_ms"] == 100
    assert _run("frame", "list", request={"sprite_file": str(target)})["frames"] == [
        {"frame_number": 1, "duration_ms": 100},
        {"frame_number": 2, "duration_ms": 100},
        {"frame_number": 3, "duration_ms": 340},
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frame_number", 0),
        ("frame_number", 4),
        ("duration_ms", 0),
        ("duration_ms", 65536),
    ],
)
def test_invalid_add_never_publishes_target(
    tmp_path: Path, field: str, value: int
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        "frame_number": 2,
        "duration_ms": 100,
    }
    request[field] = value
    result = spa(
        "frame",
        "add",
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.returncode != 0
    assert not target.exists()
    assert _run("frame", "list", request={"sprite_file": str(source)})["frames"] == [
        {"frame_number": 1, "duration_ms": 120},
        {"frame_number": 2, "duration_ms": 340},
    ]


def test_duplicate_preserves_absent_cels(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _tagged_sprite(source)
    duplicated = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 2,
            "cel_mode": "link",
        },
    )
    assert duplicated["inserted_frame"] == {"frame_number": 3, "duration_ms": 340}
    assert duplicated["source_cel_count"] == 0
    assert duplicated["inserted_cel_count"] == 0
    assert all(cel["frame_number"] != 3 for cel in duplicated["sprite"]["cels"])


@pytest.mark.parametrize("cel_mode", ["copy", "link"])
def test_duplicate_background_cel_preserves_declared_mode(
    tmp_path: Path, cel_mode: str
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run(
        "sprite",
        "create",
        request={
            "target_sprite_file": str(source),
            "width": 3,
            "height": 2,
            "color_mode": "rgb",
            "initial_layer": {
                "kind": "background",
                "background_color": {"red": 17, "green": 34, "blue": 51, "alpha": 255},
            },
            "overwrite": False,
        },
    )
    duplicated = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": cel_mode,
        },
    )
    assert duplicated["source_cel_count"] == 1
    assert duplicated["inserted_cel_count"] == 1
    assert _native_link_status(target, tmp_path / "links.json") is (cel_mode == "link")


@pytest.mark.parametrize(
    ("mode", "color"),
    [
        ("grayscale", {"kind": "grayscale", "gray": 60, "alpha": 255}),
        ("indexed", {"kind": "palette-index", "index": 1}),
    ],
)
def test_add_background_frame_accepts_color_compatible_with_sprite_mode(
    tmp_path: Path, mode: str, color: dict[str, object]
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    _run_fixture("background_modes.lua", mode=mode, out=str(source))
    added = _run(
        "frame",
        "add",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "frame_number": 2,
            "duration_ms": 100,
            "background_color": color,
        },
    )
    assert added["inserted_cel_count"] == 1
    assert added["sprite"]["metadata"]["color_mode"] == mode


def test_copy_mode_overrides_continuous_layer_policy(tmp_path: Path) -> None:
    source = tmp_path / "continuous.aseprite"
    target = tmp_path / "copy.aseprite"
    _run_fixture("continuous.lua", out=str(source))
    duplicated = _run(
        "frame",
        "duplicate",
        request={
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "source_frame_number": 1,
            "cel_mode": "copy",
        },
    )
    assert duplicated["sprite"]["layers"][0]["is_continuous"] is True
    assert _native_link_status(target, tmp_path / "links.json") is False
