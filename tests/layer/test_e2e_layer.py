"""Layer addressing and persistence through the installed CLI and real Aseprite."""

import json
from pathlib import Path

import pytest
from jsonschema import validate

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.support import clear_first_saved_layer_uuid, process_diagnostics, spa

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


def _layers_sprite(
    runtime: RuntimeObservation, target: Path, *, uuid_persistence: bool
) -> str:
    """Write the nested Layer Sprite of `layers.lua` to target.

    Return the runtime UUID that the fixture read from the Layer "duplicate"
    before it saved the Sprite.
    """
    uuid_file = target.with_suffix(".uuid")
    lua = run_lua(
        FIXTURES / "layers.lua",
        runtime,
        out=target,
        uuids=uuid_persistence,
        runtime_uuid=uuid_file,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return uuid_file.read_text(encoding="utf-8")


@pytest.mark.parametrize("persist", [False, True])
def test_layer_addresses_and_add_survive_reopen(
    runtime: RuntimeObservation, tmp_path: Path, persist: bool
) -> None:
    source = tmp_path / "source.aseprite"
    target = tmp_path / "target.aseprite"
    runtime_uuid = _layers_sprite(runtime, source, uuid_persistence=persist)
    listing = expect_success("layer list", {"sprite_file": str(source)})
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

    outcome = run(
        "layer get", {"sprite_file": str(source), "target": {"layer_name": "duplicate"}}
    )
    failure = outcome.envelope
    assert outcome.returncode == 2
    assert failure["code"] == "layer_ambiguous"

    selected = expect_success(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [3, 1]}}
    )
    assert selected["layer"]["name"] == "duplicate"
    if persist:
        by_uuid = expect_success(
            "layer get",
            {
                "sprite_file": str(source),
                "target": {"layer_uuid": selected["layer"]["layer_uuid"]},
            },
        )
        assert by_uuid["layer"]["path"] == [3, 1]
    else:
        outcome = run(
            "layer get",
            {"sprite_file": str(source), "target": {"layer_uuid": runtime_uuid}},
        )
        failure = outcome.envelope
        assert outcome.returncode == 2
        assert failure["code"] == "layer_uuid_unpersisted"

    added = expect_success(
        "layer add",
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
    assert added["persisted_reopen_verified"] is True
    assert added["layer"]["path"] == [3, 2]
    assert added["layer"]["name"] == "new-child"
    assert added["use_layer_uuids"] is persist

    reopened = expect_success("layer list", {"sprite_file": str(target)})
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


def test_layer_invalid_path_and_background_inspection(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _layers_sprite(runtime, source, uuid_persistence=False)
    outcome = run(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [2, 1]}}
    )
    failure = outcome.envelope
    assert outcome.returncode == 2
    assert failure["code"] == "layer_invalid_path"
    background = expect_success(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [1]}}
    )
    assert background["layer"]["is_background"] is True


def test_layer_add_group_and_typed_target_failures(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "source.aseprite"
    _layers_sprite(runtime, source, uuid_persistence=True)
    for address, expected in [
        ({"layer_name": "missing"}, "layer_missing"),
        ({"layer_uuid": "00000000-0000-0000-0000-000000000000"}, "layer_missing"),
        ({"layer_name": "duplicate"}, "layer_ambiguous"),
        ({"layer_path": [2]}, "layer_parent_not_group"),
        ({"layer_path": [9]}, "layer_invalid_path"),
    ]:
        destination = tmp_path / "rejected.aseprite"
        outcome = run(
            "layer add",
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
        failure = outcome.envelope
        assert outcome.returncode == 2, failure
        assert failure["code"] == expected
        schema = json.loads(spa("layer", "add", "--schema").stdout)
        validate(failure, schema["failure_schema"])
        assert not destination.exists()

    destination = tmp_path / "added-group.aseprite"
    added = expect_success(
        "layer add",
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
    assert added["layer"]["is_group"] is True
    assert added["layer"]["children"] == []
    assert added["layer"]["path"] == [3, 2]
    inspected = expect_success(
        "layer get",
        {"sprite_file": str(destination), "target": {"layer_name": "nested"}},
    )
    assert inspected["layer"]["layer_uuid"] == added["layer"]["layer_uuid"]


def test_zero_saved_uuid_is_not_exposed_as_persistent_identity(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = tmp_path / "zero-uuid.aseprite"
    _layers_sprite(runtime, source, uuid_persistence=True)
    original = expect_success("layer list", {"sprite_file": str(source)})
    old_uuid = original["layers"][1]["layer_uuid"]
    assert isinstance(old_uuid, str)
    clear_first_saved_layer_uuid(source, "duplicate")

    for _ in range(2):
        listing = expect_success("layer list", {"sprite_file": str(source)})
        assert listing["use_layer_uuids"] is True
        assert listing["layers"][1]["layer_uuid"] is None
        assert listing["layers"][2]["layer_uuid"] is not None
    selected = expect_success(
        "layer get", {"sprite_file": str(source), "target": {"layer_path": [2]}}
    )
    assert selected["layer"]["layer_uuid"] is None
    outcome = run(
        "layer get", {"sprite_file": str(source), "target": {"layer_uuid": old_uuid}}
    )
    missing = outcome.envelope
    assert outcome.returncode == 2
    assert missing["code"] == "layer_missing"
    plan_result = expect_success(
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "steps": [
                    {
                        "operation": "sprite get",
                        "input": {"inspection_scope": ["layers"]},
                    }
                ],
            },
        },
    )
    assert (
        plan_result["steps"][0]["result"]["sprite"]["layers"][1]["layer_uuid"] is None
    )
    assert plan_result["final_sprite"]["layers"][1]["layer_uuid"] is None


@pytest.mark.parametrize("persist_plan", [False, True])
@pytest.mark.parametrize("zero_saved_uuid", [False, True])
def test_plan_sprite_get_preserves_verified_layer_uuids(
    runtime: RuntimeObservation,
    tmp_path: Path,
    persist_plan: bool,
    zero_saved_uuid: bool,
) -> None:
    source = tmp_path / "source.aseprite"
    _layers_sprite(runtime, source, uuid_persistence=True)
    if zero_saved_uuid:
        clear_first_saved_layer_uuid(source, "duplicate")
    expected_layers = expect_success(
        "sprite get", {"sprite_file": str(source), "inspection_scope": ["layers"]}
    )["layers"]
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
    result = expect_success("plan run", {"plan": plan})
    assert result["steps"][0]["result"]["sprite"]["layers"] == expected_layers
    if persist_plan and zero_saved_uuid:
        assert result["final_sprite"]["layers"][1]["layer_uuid"] is not None
        target = expect_success(
            "sprite get",
            {
                "sprite_file": str(plan["target_sprite_file"]),
                "inspection_scope": ["layers"],
            },
        )
        assert result["final_sprite"]["layers"] == target["layers"]
        assert (
            result["final_sprite"]["layers"][0]["layer_uuid"]
            == (expected_layers[0]["layer_uuid"])
        )
    else:
        assert result["final_sprite"]["layers"] == expected_layers
    assert result["persisted_reopen_verified"] is persist_plan
