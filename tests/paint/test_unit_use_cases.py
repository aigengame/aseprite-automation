"""Paint use-case postconditions at the Domain Module boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from spa.contracts import Diagnostics
from spa.paint import PaintApplyRequest, apply_paint
from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    RuntimeIssue,
    RuntimeObservation,
    TargetCommitObservation,
)


def _request() -> PaintApplyRequest:
    return PaintApplyRequest.model_validate(
        {
            "source_sprite_file": "source.aseprite",
            "target_sprite_file": "target.aseprite",
            "in_place": False,
            "overwrite": False,
            "target": {"layer_path": [1], "frame_number": 1},
            "patch": {
                "coordinate_space": "image-pixel",
                "rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
                "runs": [
                    {
                        "x": 0,
                        "y": 0,
                        "length": 2,
                        "color": {
                            "kind": "rgba",
                            "red": 1,
                            "green": 2,
                            "blue": 3,
                            "alpha": 255,
                        },
                    }
                ],
            },
        }
    )


def _evidence(**overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "input_form": "inline",
        "persisted_reopen_verified": True,
        "target": {"layer_path": [1], "frame_number": 1},
        "color_mode": "rgb",
        "clipping": "reject",
        "selection": None,
        "requested_rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        "applied_rectangle": {"x": 0, "y": 0, "width": 2, "height": 1},
        "requested_runs": [
            {
                "x": 0,
                "y": 0,
                "length": 2,
                "color": {
                    "kind": "rgba",
                    "red": 1,
                    "green": 2,
                    "blue": 3,
                    "alpha": 255,
                },
            }
        ],
        "applied_runs": [
            {
                "x": 0,
                "y": 0,
                "length": 2,
                "color": {
                    "kind": "rgba",
                    "red": 1,
                    "green": 2,
                    "blue": 3,
                    "alpha": 255,
                },
            }
        ],
        "skipped_by_bounds_runs": [],
        "skipped_by_selection_runs": [],
        "pixels_requested": 2,
        "pixels_written": 2,
        "pixels_changed": 2,
        "pixels_skipped_by_bounds": 0,
        "pixels_skipped_by_selection": 0,
        "pixel_partition_verified": True,
        "affected_cels": [
            {
                "layer_path": [1],
                "frame_number": 1,
                "position": {"x": 0, "y": 0},
                "bounds": {"x": 0, "y": 0, "width": 2, "height": 1},
                "linked_to_target": True,
            }
        ],
        "linked_cels_preserved": True,
        "geometry_unchanged": True,
        "background_opaque": False,
        "effective_palettes": [],
        "before_content_digest": {"algorithm": "fnv1a64", "value": "0" * 16},
        "after_content_digest": {"algorithm": "fnv1a64", "value": "1" * 16},
    }
    result.update(overrides)
    return result


def _observation() -> RuntimeObservation:
    return RuntimeObservation(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_path="/data/gui.xml",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=(
            "aseprite_scripting",
            "lua_file_io",
            "aseprite_json",
        ),
        verified_capabilities=("aseprite_paint_apply",),
    )


@dataclass
class _TargetFiles:
    commits: int = 0
    discarded: int = 0

    def same_publication_target(self, _source: Path, _target: Path) -> bool:
        return False

    def staged_path(self, target: Path) -> Path:
        return target.with_suffix(".staged.aseprite")

    def commit(
        self, staged: Path, target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        self.commits += 1
        assert staged == Path("target.staged.aseprite")
        assert target == Path("target.aseprite")
        assert overwrite is False
        return TargetCommitObservation(str(target), 9, "2" * 64)

    def discard(self, staged: Path) -> None:
        self.discarded += 1


def _services(
    payload: dict[str, Any], files: _TargetFiles
) -> tuple[OperationServices, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def invoke(
        _observation: RuntimeObservation,
        _handler: object,
        request_payload: dict[str, Any],
        _timeout: float,
    ) -> KernelInvocationResult:
        calls.append(request_payload)
        return KernelInvocationResult(
            payload=payload,
            response_path="/response.json",
            diagnostics=Diagnostics(exit_status=0),
        )

    return (
        OperationServices(
            probe_runtime=lambda _request: _observation(),
            invoke_kernel=invoke,
            target_files=files,
        ),
        calls,
    )


def test_apply_commits_only_validated_persisted_evidence() -> None:
    files = _TargetFiles()
    services, calls = _services(_evidence(), files)

    result = apply_paint(_request(), services)

    assert result.target_commit.target_sprite_file == "target.aseprite"
    assert result.persisted_reopen_verified is True
    assert files.commits == 1
    assert files.discarded == 1
    assert calls == [
        {
            "source_sprite_file": "source.aseprite",
            "target": {"layer_path": [1], "frame_number": 1},
            "patch": _request().patch.model_dump(mode="json"),
            "clipping": "reject",
            "selection": None,
            "staged_sprite_file": "target.staged.aseprite",
        }
    ]


def test_apply_accepts_changed_pixels_when_content_digests_collide() -> None:
    files = _TargetFiles()
    digest = {"algorithm": "fnv1a64", "value": "0" * 16}
    services, _ = _services(
        _evidence(before_content_digest=digest, after_content_digest=digest), files
    )

    result = apply_paint(_request(), services)

    assert result.pixels_changed == 2
    assert result.before_content_digest == result.after_content_digest
    assert files.commits == 1


def test_apply_refuses_malformed_evidence_before_target_commit() -> None:
    files = _TargetFiles()
    services, _ = _services(_evidence(persisted_reopen_verified=False), files)

    with pytest.raises(RuntimeIssue) as failure:
        apply_paint(_request(), services)

    assert failure.value.kind == "response_malformed"
    assert files.commits == 0
    assert files.discarded == 1


def test_apply_refuses_incoherent_pixel_accounting_before_target_commit() -> None:
    files = _TargetFiles()
    services, _ = _services(_evidence(pixels_written=1), files)

    with pytest.raises(RuntimeIssue) as failure:
        apply_paint(_request(), services)

    assert failure.value.kind == "postcondition_failed"
    assert files.commits == 0
    assert files.discarded == 1


def test_apply_refuses_false_digest_postcondition_before_target_commit() -> None:
    files = _TargetFiles()
    services, _ = _services(
        _evidence(
            pixels_changed=0,
            before_content_digest={"algorithm": "fnv1a64", "value": "0" * 16},
            after_content_digest={"algorithm": "fnv1a64", "value": "1" * 16},
        ),
        files,
    )

    with pytest.raises(RuntimeIssue) as failure:
        apply_paint(_request(), services)

    assert failure.value.kind == "postcondition_failed"
    assert files.commits == 0
    assert files.discarded == 1
