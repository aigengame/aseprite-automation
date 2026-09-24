"""Layer addressing and persistence through the installed CLI and real Aseprite."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from spa.runtime.invocation import prepare_invocation
from tests.support import spa

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
    assert run.returncode == 0, run.stderr
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
    assert failure["details"]["errors"][0]["code"] == "layer_ambiguous"

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
        assert failure["details"]["errors"][0]["code"] == "layer_uuid_unpersisted"

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
    assert failure["details"]["errors"][0]["code"] == "layer_invalid_path"
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
        assert failure["details"]["errors"][0]["code"] == expected
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
