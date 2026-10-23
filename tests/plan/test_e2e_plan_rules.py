"""Plan rule table: each Plan-eligible Operation keeps its standalone semantics in a Plan.

- R1: a Step result equals the standalone result, after the projection of its result
  family removes the fields that only one side has.
- R2: a Step refusal has the standalone code and details, plus `step_number`.

The guards at the end are fast: they compare the table with the Plan-eligible
descriptors. Each case names the Lua fixture that writes its Source.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from spa.application.plan import ELIGIBLE_OPERATIONS
from spa.contracts.operation import RUNTIME_FAILURE_CODES
from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import expect_success, run, run_lua
from tests.plan.support import red_pixel
from tests.support import icc_fixture_path, motion_curves, process_diagnostics

TESTS = Path(__file__).parents[1]


@dataclass(frozen=True)
class Fixture:
    """A Lua fixture that writes a Source Sprite to its output parameter."""

    script: Path
    output: str
    params: tuple[tuple[str, str], ...] = ()

    def write(self, runtime: RuntimeObservation, source: Path) -> Path:
        lua = run_lua(
            self.script, runtime, **{self.output: source}, **dict(self.params)
        )
        assert lua.returncode == 0, process_diagnostics(lua)
        assert source.is_file()
        return source


TAGGED = Fixture(TESTS / "frame/fixtures/tagged.lua", "out")
CELS = Fixture(TESTS / "cel/fixtures/cels.lua", "out")
POSES = Fixture(TESTS / "motion/fixtures/poses.lua", "out")
MISSING_POSE = Fixture(POSES.script, "out", (("kind", "missing"),))
RGB_INK = Fixture(
    TESTS / "color_mode/fixtures/source.lua", "source", (("mode", "rgb"),)
)
SRGB_PROFILE = Fixture(
    TESTS / "color/fixtures/profile_sprite.lua", "source", (("action", "create"),)
)
TILESETS = Fixture(TESTS / "plan/fixtures/tileset_lifecycle.lua", "source")
CONVERTER = "aseprite_convert_color_profile"


@dataclass(frozen=True)
class Case:
    """One Step of operation on the Source of fixture (None: the Step creates it)."""

    operation: str
    fixture: Fixture | None
    step_input: dict[str, Any]
    reads: bool = False
    capability: str | None = None


def _icc(identity: str) -> dict[str, str]:
    return {"kind": "icc", "icc_file": str(icc_fixture_path(identity))}


def _cel(layer: int, frame: int) -> dict[str, Any]:
    return {"layer": {"layer_path": [layer]}, "frame_number": frame}


ALL_SECTIONS = ["frames", "tags", "palettes", "layers", "cels", "slices", "tilesets"]
CASES = {
    case.operation: case
    for case in (
        Case(
            "sprite create",
            None,
            {
                "width": 3,
                "height": 2,
                "color_mode": "rgb",
                "initial_layer": {"kind": "transparent"},
            },
        ),
        Case("sprite get", TAGGED, {"inspection_scope": ALL_SECTIONS}, reads=True),
        Case(
            "sprite assign-color-profile",
            SRGB_PROFILE,
            {"profile": _icc("linear_srgb")},
        ),
        Case(
            "sprite convert-color-profile",
            SRGB_PROFILE,
            {"profile": _icc("linear_srgb")},
            capability=CONVERTER,
        ),
        Case("paint apply", RGB_INK, red_pixel(2)),
        Case("frame list", TAGGED, {}, reads=True),
        Case("frame get", TAGGED, {"frame_number": 2}, reads=True),
        Case("frame add", TAGGED, {"frame_number": 2, "duration_ms": 340}),
        Case("frame duplicate", TAGGED, {"source_frame_number": 1, "cel_mode": "link"}),
        Case("cel add", CELS, {"target": _cel(1, 1)}),
        Case(
            "cel set",
            CELS,
            {
                "target": _cel(1, 3),
                "position": {"x": -2, "y": 3},
                "opacity": 0,
                "z_index": -1,
            },
        ),
        Case("motion apply", POSES, motion_curves()),
        Case(
            "sprite change-color-mode",
            RGB_INK,
            {
                "conversion": {
                    "source_color_mode": "rgb",
                    "target": {
                        "color_mode": "indexed",
                        "rgb_map_algorithm": "default",
                        "color_best_fit_criteria": "default",
                        "dithering": {
                            "algorithm": "ordered",
                            "matrix": {"kind": "installed", "id": "bayer4x4"},
                        },
                    },
                }
            },
        ),
        Case("tileset remove", TILESETS, {"target": {"tileset_index": 2}}),
        Case(
            "layer set-tileset",
            TILESETS,
            {
                "layer": {"layer_name": "map"},
                "target": {"tileset_index": 2},
                "mapping": {"kind": "by_key"},
                "grid_policy": "require_equal",
            },
        ),
    )
}

# R1 projections, from the result schemas: the fields that only the Step result or
# only the standalone result of a family has. A mutation Step result keeps its live
# facts (`persisted_reopen_verified` is false and `sprite` is null); the Plan result
# owns the Target Commit. A read Step result has no file or envelope fields.
MUTATION_ONE_SIDED = {
    "status",
    "operation",
    "target_commit",
    "persisted_reopen_verified",
    "sprite",
}
READ_ONE_SIDED = {"status", "operation", "sprite_file"}
# Findings: these Operations do not fit their family projection. The values are
# the fields that still differ after the projection. The PR records them as open.
MISFITS = {
    # The Step result has `initial_layer`; the standalone result has
    # `persisted_initial_layer`. The projection also removes `sprite`, the main
    # fact, and the live Step palette differs from the persisted one.
    "sprite create": {"initial_layer", "persisted_initial_layer"},
    # The Step result nests the read sections under `sprite`.
    "sprite get": {"sprite", "metadata", *ALL_SECTIONS},
}


@dataclass(frozen=True)
class Refusal:
    """A Step input on the Source of fixture that the Kernel refuses with code."""

    operation: str
    fixture: Fixture
    step_input: dict[str, Any]
    code: str
    capability: str | None = None


REFUSALS = (
    Refusal(
        "sprite convert-color-profile",
        SRGB_PROFILE,
        {"profile": _icc("display_p3_cc0")},
        "color_profile_file_failed",
        CONVERTER,
    ),
    Refusal("paint apply", CELS, red_pixel(), "cel_not_found"),
    Refusal("cel add", CELS, {"target": _cel(1, 2)}, "cel_already_exists"),
    Refusal("cel set", CELS, {"target": _cel(1, 1), "opacity": 0}, "cel_not_found"),
    Refusal("motion apply", MISSING_POSE, motion_curves(), "cel_not_found"),
    Refusal(
        "sprite change-color-mode",
        RGB_INK,
        {
            "conversion": {
                "source_color_mode": "grayscale",
                "target": {"color_mode": "rgb"},
            }
        },
        "color_mode_mismatch",
    ),
    Refusal(
        "tileset remove", TILESETS, {"target": {"tileset_index": 1}}, "tileset_in_use"
    ),
    Refusal(
        "layer set-tileset",
        TILESETS,
        {
            "layer": {"layer_name": "map"},
            "target": {"tileset_index": 9},
            "mapping": {"kind": "by_key"},
            "grid_policy": "require_equal",
        },
        "tileset_missing",
    ),
)
# Its typed refusals come before the Kernel (fast tier). The native refusal needs an
# ICC that passes verification but that Aseprite cannot load.
PREFLIGHT_REFUSAL_ONLY = {"sprite assign-color-profile"}

SPRITE_GET_FRAMES = {
    "operation": "sprite get",
    "input": {"inspection_scope": ["frames"]},
}


def _require(capability: str | None, runtime: RuntimeObservation) -> None:
    if capability and capability not in runtime.verified_capabilities:
        assert sys.platform == "linux", f"expected the {capability} capability"
        pytest.skip(f"selected Linux runtime has no {capability} capability")


def _source(
    fixture: Fixture | None, runtime: RuntimeObservation, tmp_path: Path
) -> Path | None:
    return (
        None
        if fixture is None
        else fixture.write(runtime, tmp_path / "source.aseprite")
    )


def _standalone(
    operation: str, source: Path | None, target: Path, step_input: dict[str, Any]
) -> dict[str, Any]:
    """Return the standalone request of a Step input."""
    if source is None:
        return {"target_sprite_file": str(target), "overwrite": False, **step_input}
    if "sprite_file" in ELIGIBLE_OPERATIONS[operation].request_type.model_fields:
        return {"sprite_file": str(source), **step_input}
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": False,
        "overwrite": False,
        **step_input,
    }


def _plan(source: Path | None, target: Path | None, steps: list[dict]) -> dict:
    """Return a `plan run` request; an existing Target is overwritten."""
    body: dict[str, Any] = {"steps": steps}
    if source is not None:
        body["source_sprite_file"] = str(source)
    if target is not None:
        body["target_sprite_file"] = str(target)
        body["in_place"] = source == target
        body["overwrite"] = target.exists()
    return {"plan": body}


def _step(case: Case) -> dict[str, Any]:
    return {"operation": case.operation, "input": case.step_input}


_ABSENT = object()


def _differing(step: dict, standalone: dict, one_sided: set[str]) -> set[str]:
    """Return the fields, except one_sided, that differ or that one side does not have."""
    keys = (step.keys() | standalone.keys()) - one_sided
    return {
        key for key in keys if step.get(key, _ABSENT) != standalone.get(key, _ABSENT)
    }


@pytest.mark.e2e
@pytest.mark.parametrize("operation", sorted(CASES))
def test_r1_step_result_equals_standalone_result(
    operation: str, runtime: RuntimeObservation, tmp_path: Path
) -> None:
    case = CASES[operation]
    _require(case.capability, runtime)
    source = _source(case.fixture, runtime, tmp_path)
    frozen = None if source is None else source.read_bytes()
    alone, planned = tmp_path / "standalone.aseprite", tmp_path / "planned.aseprite"
    expected = expect_success(
        operation, _standalone(operation, source, alone, case.step_input)
    )

    result = expect_success(
        "plan run", _plan(source, None if case.reads else planned, [_step(case)])
    )
    step = result["steps"][0]["result"]
    one_sided = READ_ONE_SIDED if case.reads else MUTATION_ONE_SIDED
    assert _differing(step, expected, one_sided) == MISFITS.get(operation, set())
    if operation == "sprite get":
        sections = MISFITS[operation] - {"sprite"}
        assert step["sprite"] == {key: expected[key] for key in sections}
    if operation == "sprite create":
        assert step["initial_layer"] == expected["persisted_initial_layer"]
    if case.reads:
        assert result["target_commit"] is None
    else:
        assert step.get("persisted_reopen_verified", False) is False
        assert result["persisted_reopen_verified"] is True
        assert expected["persisted_reopen_verified"] is True
    assert source is None or source.read_bytes() == frozen


@pytest.mark.e2e
@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda refusal: refusal.operation)
def test_r2_step_refusal_equals_standalone_refusal(
    refusal: Refusal, runtime: RuntimeObservation, tmp_path: Path
) -> None:
    _require(refusal.capability, runtime)
    source = refusal.fixture.write(runtime, tmp_path / "source.aseprite")
    frozen = source.read_bytes()
    alone, planned = tmp_path / "standalone.aseprite", tmp_path / "planned.aseprite"
    standalone = run(
        refusal.operation,
        _standalone(refusal.operation, source, alone, refusal.step_input),
    )
    assert standalone.returncode == 2, standalone.envelope
    assert standalone.envelope["code"] == refusal.code

    step = {"operation": refusal.operation, "input": refusal.step_input}
    outcome = run("plan run", _plan(source, planned, [SPRITE_GET_FRAMES, step]))
    failure = outcome.envelope
    assert outcome.returncode == 2, failure
    assert failure["code"] == refusal.code
    assert failure["details"] == standalone.envelope["details"] | {"step_number": 2}
    assert source.read_bytes() == frozen
    assert not alone.exists() and not planned.exists()


def test_rule_table_covers_each_plan_eligible_operation() -> None:
    assert set(CASES) == set(ELIGIBLE_OPERATIONS)
    for operation, case in CASES.items():
        fields = ELIGIBLE_OPERATIONS[operation].request_type.model_fields
        assert case.reads == ("sprite_file" in fields), operation
    assert set(MISFITS) <= set(CASES)


def test_refusal_rows_cover_each_operation_with_a_typed_refusal() -> None:
    common = {*RUNTIME_FAILURE_CODES, "target_commit_failed"}
    typed = {
        name
        for name, descriptor in ELIGIBLE_OPERATIONS.items()
        if set(descriptor.failure_codes) - common
    }
    rows = {refusal.operation for refusal in REFUSALS}
    assert len(rows) == len(REFUSALS)
    assert rows | PREFLIGHT_REFUSAL_ONLY == typed
    assert not rows & PREFLIGHT_REFUSAL_ONLY
    for refusal in REFUSALS:
        codes = ELIGIBLE_OPERATIONS[refusal.operation].failure_codes
        assert refusal.code in set(codes) - common
