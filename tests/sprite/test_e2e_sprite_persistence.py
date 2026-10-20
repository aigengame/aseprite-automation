"""Ownership and native facts at the shared Sprite persistence boundary."""

import json
from collections import Counter
from importlib.resources import files
from pathlib import Path

import pytest

from spa.authoring.document.sprite import SPRITE_INSPECTION_RESOURCES
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run_lua
from tests.support import motion_curves, motion_sprite, observe_cli, process_diagnostics

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"
OBSERVER = FIXTURES / "observe_persistence_cli.py"


@pytest.mark.parametrize(
    ("entry_point", "nested"),
    [
        ("equal", False),
        ("equal", True),
        ("assert_equal", False),
        ("assert_equal", True),
        ("assert_same", False),
    ],
)
def test_shared_persistence_compares_slice_facts_and_multiplicities(
    runtime: RuntimeObservation, entry_point: str, nested: bool
) -> None:
    lua = run_lua(
        FIXTURES / "compare_slice_facts.lua",
        runtime,
        persistence=files("spa.kernel").joinpath(
            "document/sprite/sprite_persistence.lua"
        ),
        entry_point=entry_point,
        nested=nested,
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def test_tag_add_preserves_color_distinct_slices_across_native_reordering(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    source, target = tmp_path / "source.aseprite", tmp_path / "target.aseprite"
    lua = run_lua(FIXTURES / "reordered_slices.lua", runtime, out=source)
    assert lua.returncode == 0, process_diagnostics(lua)
    source_bytes = source.read_bytes()
    before = expect_success(
        "sprite get", {"sprite_file": str(source), "inspection_scope": ["slices"]}
    )
    assert len(before["slices"]) == 2
    assert {item["color"]["red"] for item in before["slices"]} == {0, 12}
    added = expect_success(
        "tag add",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "name": "new",
            "from_frame": 1,
            "to_frame": 2,
            "direction": "forward",
            "repeats": 0,
        },
    )
    assert added["persisted_reopen_verified"] is True
    assert added["tag"]["name"] == "new"
    after = expect_success(
        "sprite get", {"sprite_file": str(target), "inspection_scope": ["slices"]}
    )
    assert Counter(
        json.dumps(item, sort_keys=True) for item in after["slices"]
    ) == Counter(json.dumps(item, sort_keys=True) for item in before["slices"])
    assert source.read_bytes() == source_bytes


def run_verified_save(runtime: RuntimeObservation, tmp_path: Path, case: str) -> None:
    """Run the verified-save fixture with the Kernel persistence and inspection files."""
    kernel = files("spa.kernel")
    lua = run_lua(
        FIXTURES / "verified_save.lua",
        runtime,
        persistence=kernel.joinpath("document/sprite/sprite_persistence.lua"),
        **{
            resource.parameter_name: kernel.joinpath(resource.package_path)
            for resource in SPRITE_INSPECTION_RESOURCES
        },
        digest=kernel.joinpath("foundation/digest.lua"),
        staged=tmp_path / "staged.aseprite",
        case=case,
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def test_verified_save_transfers_ownership_and_returns_fresh_facts(
    runtime: RuntimeObservation,
    tmp_path: Path,
) -> None:
    run_verified_save(runtime, tmp_path, "success")
    assert (tmp_path / "staged.aseprite").is_file()


@pytest.mark.parametrize("case", ["save", "reopen", "observation", "comparison"])
def test_verified_save_closes_owned_sprites_on_failure(
    runtime: RuntimeObservation,
    tmp_path: Path,
    case: str,
) -> None:
    run_verified_save(runtime, tmp_path, case)


@pytest.mark.parametrize("operation", ["cel set", "motion apply"])
@pytest.mark.parametrize(
    "case", ["success", "save", "reopen", "observation", "comparison"]
)
@pytest.mark.parametrize("in_place", [False, True])
def test_handlers_gate_commit_and_restore_editor_on_persistence_failure(
    runtime: RuntimeObservation,
    tmp_path: Path,
    operation: str,
    case: str,
    in_place: bool,
) -> None:
    source = motion_sprite(runtime, tmp_path, uuids="true")
    target = source if in_place else tmp_path / "existing.aseprite"
    if not in_place:
        target.write_bytes(b"prior Target")
    before_source, before_target = source.read_bytes(), target.read_bytes()
    inputs = (
        motion_curves()
        if operation == "motion apply"
        else {
            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
            "opacity": 42,
        }
    )
    request = {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": in_place,
        "overwrite": True,
        **inputs,
    }
    _, outcome, observations = observe_cli(
        OBSERVER, case, operation, request, tmp_path / "observations.json"
    )
    assert observations["handler_invocations"] == observations["saves"] == 1
    assert observations["probe_invocations"] == 1
    assert observations["editor_restored"] is True
    assert observations["owned_sprites_closed"] is True
    if case == "success":
        assert outcome["status"] == "success", outcome
        assert outcome["persisted_reopen_verified"] is True
        assert observations["commits"] == 1
        assert observations["staged_opens"] == 2
    else:
        assert outcome["code"] == "kernel_execution_failed", outcome
        reasons = {
            "save": "could not save staged Sprite",
            "reopen": "could not reopen staged Sprite",
            "observation": "could not reopen Sprite for UUID verification",
            "comparison": "differs at document",
        }
        assert reasons[case] in outcome["details"]["reason"]
        assert (
            observations["staged_opens"]
            == {
                "save": 0,
                "reopen": 1,
                "observation": 2,
                "comparison": 2,
            }[case]
        )
        assert observations["commits"] == 0
        assert source.read_bytes() == before_source
        assert target.read_bytes() == before_target
    if not in_place:
        assert source.read_bytes() == before_source
    assert not list(tmp_path.glob(".*.staged.aseprite"))


def test_cel_and_motion_plan_saves_only_after_all_steps(
    runtime: RuntimeObservation, tmp_path: Path
) -> None:
    source = motion_sprite(runtime, tmp_path, uuids="true")
    before_source = source.read_bytes()
    _, outcome, observations = observe_cli(
        OBSERVER,
        "success",
        "plan run",
        {
            "plan": {
                "source_sprite_file": str(source),
                "target_sprite_file": str(tmp_path / "planned.aseprite"),
                "steps": [
                    {
                        "operation": "cel set",
                        "input": {
                            "target": {"layer": {"layer_path": [1]}, "frame_number": 1},
                            "opacity": 42,
                        },
                    },
                    {"operation": "motion apply", "input": motion_curves()},
                ],
            },
        },
        tmp_path / "observations.json",
    )
    assert outcome["status"] == "success", outcome
    assert outcome["persisted_reopen_verified"] is True
    assert all(
        step["result"]["persisted_reopen_verified"] is False
        for step in outcome["steps"]
    )
    assert observations == {
        "handler_invocations": 1,
        "probe_invocations": 0,
        "commits": 1,
        "saves": 1,
        "staged_opens": 2,
        "editor_restored": True,
        "owned_sprites_closed": True,
    }
    assert source.read_bytes() == before_source
