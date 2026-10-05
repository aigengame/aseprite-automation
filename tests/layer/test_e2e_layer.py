"""Layer addressing and persistence through the installed CLI and real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from jsonschema import validate

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import clear_first_saved_layer_uuid, process_diagnostics, spa

pytestmark = pytest.mark.e2e


def _fixture(target: Path, *, uuid_persistence: bool) -> str:
    aseprite = Path(os.environ["SPA_TEST_ASEPRITE"]).resolve()
    resource = aseprite.parent.parent / "Resources" / "data" / "gui.xml"
    script = Path(__file__).parent / "fixtures" / "layers.lua"
    uuid_file = target.with_suffix(".uuid")
    with tempfile.TemporaryDirectory(prefix="spa-layer-fixture-") as work:
        prepared = prepare_invocation(aseprite, resource, Path(work))
        run = subprocess.run(
            [
                str(prepared.executable),
                "--batch",
                "--script-param",
                f"out={target}",
                "--script-param",
                f"uuids={'true' if uuid_persistence else 'false'}",
                "--script-param",
                f"runtime_uuid={uuid_file}",
                "--script",
                str(script),
            ],
            text=True,
            capture_output=True,
            env=prepared.environment,
            check=False,
        )
    assert run.returncode == 0, process_diagnostics(run)
    return uuid_file.read_text(encoding="utf-8")


def _run(command: str, request: dict[str, object]) -> tuple[int, dict]:
    request["aseprite"] = os.environ["SPA_TEST_ASEPRITE"]
    result = spa("layer", command, "--input-json", json.dumps(request))
    return result.returncode, json.loads(result.stdout)


@pytest.mark.parametrize("persist", [False, True])
def test_layer_addresses_and_add_survive_reopen(tmp_path: Path, persist: bool) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    runtime_uuid = _fixture(source, uuid_persistence=persist)
    code, listing = _run("list", {"sprite_file": str(source)})
    assert code == 0, listing
    assert listing["use_layer_uuids"] is persist
    assert len(listing["layers"]) == 3
    group = listing["layers"][2]
    assert group["is_group"] is True
    assert group["path"] == [3]
    assert group["children"][0]["path"] == [3, 1]
    assert group["children"][0]["name"] == "duplicate"
    assert (group["layer_uuid"] is not None) is persist
    assert all(
        (layer["layer_uuid"] is not None) is persist for layer in listing["layers"]
    )

    code, failure = _run(
        "get", {"sprite_file": str(source), "target": {"layer_name": "duplicate"}}
    )
    assert code == 2
    assert failure["code"] == "layer_ambiguous"

    code, selected = _run(
        "get", {"sprite_file": str(source), "target": {"layer_path": [3, 1]}}
    )
    assert code == 0, selected
    assert selected["layer"]["name"] == "duplicate"
    if persist:
        code, by_uuid = _run(
            "get",
            {
                "sprite_file": str(source),
                "target": {"layer_uuid": selected["layer"]["layer_uuid"]},
            },
        )
        assert code == 0, by_uuid
        assert by_uuid["layer"]["path"] == [3, 1]
    else:
        code, failure = _run(
            "get",
            {"sprite_file": str(source), "target": {"layer_uuid": runtime_uuid}},
        )
        assert code == 2
        assert failure["code"] == "layer_uuid_unpersisted"

    code, added = _run(
        "add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "kind": "transparent",
            "name": "new-child",
            "parent": {"layer_name": "parent"},
        },
    )
    assert code == 0, added
    assert added["persisted_reopen_verified"] is True
    assert added["layer"]["path"] == [3, 2]
    assert added["layer"]["name"] == "new-child"
    assert added["use_layer_uuids"] is persist

    code, reopened = _run("list", {"sprite_file": str(target)})
    assert code == 0, reopened
    assert reopened["use_layer_uuids"] is persist
    assert reopened["layers"][2]["children"][1]["path"] == [3, 2]
    assert (
        reopened["layers"][2]["children"][1]["layer_uuid"]
        == added["layer"]["layer_uuid"]
    )
    if persist:
        assert (
            reopened["layers"][2]["children"][0]["layer_uuid"]
            == selected["layer"]["layer_uuid"]
        )


def test_layer_invalid_path_and_background_inspection(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, uuid_persistence=False)
    code, failure = _run(
        "get", {"sprite_file": str(source), "target": {"layer_path": [2, 1]}}
    )
    assert code == 2
    assert failure["code"] == "layer_invalid_path"
    code, background = _run(
        "get", {"sprite_file": str(source), "target": {"layer_path": [1]}}
    )
    assert code == 0, background
    assert background["layer"]["is_background"] is True


def test_layer_add_group_and_typed_target_failures(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, uuid_persistence=True)
    for address, expected in [
        ({"layer_name": "missing"}, "layer_missing"),
        ({"layer_uuid": "00000000-0000-0000-0000-000000000000"}, "layer_missing"),
        ({"layer_name": "duplicate"}, "layer_ambiguous"),
        ({"layer_path": [2]}, "layer_parent_not_group"),
        ({"layer_path": [9]}, "layer_invalid_path"),
    ]:
        destination = tmp_path / "rejected.aseprite"
        code, failure = _run(
            "add",
            {
                "source_sprite_file": str(source),
                "target_sprite_file": str(destination),
                "in_place": False,
                "overwrite": False,
                "kind": "group",
                "name": "nested",
                "parent": address,
            },
        )
        assert code == 2, failure
        assert failure["code"] == expected
        schema = json.loads(spa("layer", "add", "--schema").stdout)
        validate(failure, schema["failure_schema"])
        assert not destination.exists()

    destination = tmp_path / "added-group.aseprite"
    code, added = _run(
        "add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(destination),
            "in_place": False,
            "overwrite": False,
            "kind": "group",
            "name": "nested",
            "parent": {"layer_path": [3]},
        },
    )
    assert code == 0, added
    assert added["layer"]["is_group"] is True
    assert added["layer"]["children"] == []
    assert added["layer"]["path"] == [3, 2]
    code, inspected = _run(
        "get", {"sprite_file": str(destination), "target": {"layer_name": "nested"}}
    )
    assert code == 0, inspected
    assert inspected["layer"]["layer_uuid"] == added["layer"]["layer_uuid"]


def test_zero_saved_uuid_is_not_exposed_as_persistent_identity(tmp_path: Path) -> None:
    source = tmp_path / "zero-uuid.aseprite"
    _fixture(source, uuid_persistence=True)
    code, original = _run("list", {"sprite_file": str(source)})
    assert code == 0
    old_uuid = original["layers"][1]["layer_uuid"]
    assert isinstance(old_uuid, str)
    clear_first_saved_layer_uuid(source, "duplicate")

    for _ in range(2):
        code, listing = _run("list", {"sprite_file": str(source)})
        assert code == 0, listing
        assert listing["use_layer_uuids"] is True
        assert listing["layers"][1]["layer_uuid"] is None
        assert listing["layers"][2]["layer_uuid"] is not None
    code, selected = _run(
        "get", {"sprite_file": str(source), "target": {"layer_path": [2]}}
    )
    assert code == 0, selected
    assert selected["layer"]["layer_uuid"] is None
    code, missing = _run(
        "get", {"sprite_file": str(source), "target": {"layer_uuid": old_uuid}}
    )
    assert code == 2
    assert missing["code"] == "layer_missing"
    plan = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "plan": {
                    "source_sprite_file": str(source),
                    "steps": [
                        {
                            "operation": "sprite get",
                            "input": {"inspection_scope": ["layers"]},
                        }
                    ],
                },
            }
        ),
    )
    assert plan.returncode == 0, plan.stdout + plan.stderr
    plan_result = json.loads(plan.stdout)
    assert (
        plan_result["steps"][0]["result"]["sprite"]["layers"][1]["layer_uuid"] is None
    )
    assert plan_result["final_sprite"]["layers"][1]["layer_uuid"] is None


@pytest.mark.parametrize("persist_plan", [False, True])
@pytest.mark.parametrize("zero_saved_uuid", [False, True])
def test_plan_sprite_get_preserves_verified_layer_uuids(
    tmp_path: Path, persist_plan: bool, zero_saved_uuid: bool
) -> None:
    source = tmp_path / "source.aseprite"
    _fixture(source, uuid_persistence=True)
    if zero_saved_uuid:
        clear_first_saved_layer_uuid(source, "duplicate")
    direct = spa(
        "sprite",
        "get",
        "--input-json",
        json.dumps(
            {
                "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                "sprite_file": str(source),
                "inspection_scope": ["layers"],
            }
        ),
    )
    assert direct.returncode == 0, direct.stdout + direct.stderr
    expected_layers = json.loads(direct.stdout)["layers"]
    assert expected_layers[2]["children"][0]["layer_uuid"] is not None
    if zero_saved_uuid:
        assert expected_layers[1]["layer_uuid"] is None

    plan: dict[str, object] = {
        "source_sprite_file": str(source),
        "steps": [
            {"operation": "sprite get", "input": {"inspection_scope": ["layers"]}}
        ],
    }
    if persist_plan:
        plan["target_sprite_file"] = str(tmp_path / "target.aseprite")
        plan["steps"] = [
            *plan["steps"],
            {
                "operation": "paint apply",
                "input": {
                    "target": {"layer_path": [1], "frame_number": 1},
                    "patch": {
                        "coordinate_space": "image-pixel",
                        "rectangle": {"x": 0, "y": 0, "width": 1, "height": 1},
                        "runs": [
                            {
                                "x": 0,
                                "y": 0,
                                "length": 1,
                                "color": {
                                    "kind": "rgba",
                                    "red": 255,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 255,
                                },
                            }
                        ],
                    },
                },
            },
        ]
    run = spa(
        "plan",
        "run",
        "--input-json",
        json.dumps({"aseprite": os.environ["SPA_TEST_ASEPRITE"], "plan": plan}),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result["steps"][0]["result"]["sprite"]["layers"] == expected_layers
    if persist_plan and zero_saved_uuid:
        assert result["final_sprite"]["layers"][1]["layer_uuid"] is not None
        target = spa(
            "sprite",
            "get",
            "--input-json",
            json.dumps(
                {
                    "aseprite": os.environ["SPA_TEST_ASEPRITE"],
                    "sprite_file": str(plan["target_sprite_file"]),
                    "inspection_scope": ["layers"],
                }
            ),
        )
        assert target.returncode == 0, target.stdout + target.stderr
        assert result["final_sprite"]["layers"] == json.loads(target.stdout)["layers"]
        assert (
            result["final_sprite"]["layers"][0]["layer_uuid"]
            == (expected_layers[0]["layer_uuid"])
        )
    else:
        assert result["final_sprite"]["layers"] == expected_layers
    assert result["persisted_reopen_verified"] is persist_plan
