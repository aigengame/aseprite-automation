"""Selection refusals that Python decides, before the Kernel."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from tests.host_permissions import symlink_creation_permission
from tests.native_invocation import Outcome, run
from tests.support import probe_only_aseprite

MASK = {
    "kind": "mask",
    "bounds": {"x": 10, "y": 20, "width": 4, "height": 2},
    "rows": [
        {"y": 20, "runs": [{"x": 10, "length": 1}]},
        {"y": 21, "runs": [{"x": 10, "length": 4}]},
    ],
}


@pytest.fixture
def windows_selection_directory():
    """Keep tilde inputs under home without changing the native launch environment."""
    assert os.name == "nt"
    with tempfile.TemporaryDirectory(
        prefix="spa-selection-", dir=Path.home()
    ) as directory:
        yield Path(directory)


def selection(aseprite: Path, operation: str, **values) -> Outcome:
    """Run a Selection command; the Kernel refuses each call except the probe."""
    return run(
        f"selection {operation}",
        {"coordinate_space": "canvas-pixel", **values},
        aseprite=aseprite,
    )


@pytest.mark.parametrize(
    ("value", "space", "finding"),
    [
        (
            {**MASK, "rows": list(reversed(MASK["rows"]))},
            "canvas-pixel",
            "selection_encoding_invalid",
        ),
        (MASK, "image-pixel", "selection_coordinate_space_invalid"),
    ],
)
def test_validate_returns_findings_without_repair(tmp_path, value, space, finding):
    outcome = selection(
        probe_only_aseprite(tmp_path),
        "validate",
        selection=value,
        coordinate_space=space,
        canvas=None,
    )
    assert outcome.returncode == 0, outcome.envelope
    assert outcome.envelope["valid"] is False
    assert finding in {item["kind"] for item in outcome.envelope["findings"]}


def test_invalid_artifact_is_a_finding_for_validate_and_failure_for_consumers(
    tmp_path,
) -> None:
    artifact_file = tmp_path / "invalid.json"
    artifact_file.write_text('{"kind":"mask","rows":[]}')
    artifact = {"kind": "artifact", "path": str(artifact_file)}
    aseprite = probe_only_aseprite(tmp_path)
    entries = set(tmp_path.iterdir())

    validated = selection(aseprite, "validate", selection=artifact)
    assert validated.returncode == 0 and validated.envelope["valid"] is False
    assert validated.envelope["findings"][0]["kind"] == "selection_encoding_invalid"

    exported = selection(
        aseprite,
        "export",
        selection=artifact,
        destination={"path": str(tmp_path / "out.json"), "if_exists": "fail"},
    )
    assert exported.returncode != 0, exported.envelope
    assert exported.envelope["code"] == "selection_invalid"
    assert set(tmp_path.iterdir()) == entries
    assert artifact_file.read_text() == '{"kind":"mask","rows":[]}'


@pytest.mark.parametrize("operation", ["export", "preview"])
@pytest.mark.parametrize("source_kind", ["direct", "symlink"])
@pytest.mark.parametrize("spelling", ["absolute", "tilde"])
def test_artifact_input_alias_is_not_replaced(
    tmp_path, request, operation, source_kind, spelling
) -> None:
    if os.name == "nt" and spelling == "tilde":
        tmp_path = request.getfixturevalue("windows_selection_directory")
    target = tmp_path / ("mask.png" if operation == "preview" else "mask.json")
    target.write_text(json.dumps(MASK, indent=2))
    source = target
    if source_kind == "symlink":
        source = tmp_path / "input.json"
        with symlink_creation_permission():
            source.symlink_to(target)
    source_path = (
        str(Path("~") / os.path.relpath(source, Path.home()))
        if spelling == "tilde"
        else str(source)
    )
    assert Path(source_path).expanduser().samefile(source)
    aseprite = probe_only_aseprite(tmp_path)
    entries = set(tmp_path.iterdir())
    before = target.read_bytes()
    parameters = {"canvas": MASK["bounds"]} if operation == "preview" else {}
    outcome = run(
        f"selection {operation}",
        {
            "coordinate_space": "canvas-pixel",
            "selection": {"kind": "artifact", "path": source_path},
            "destination": {"path": str(target), "if_exists": "replace"},
            **parameters,
        },
        aseprite=aseprite,
    )
    assert outcome.returncode != 0, outcome.envelope
    assert outcome.envelope["code"] == "artifact_file_failed"
    assert outcome.envelope["details"]["reason"] == "source_destination_alias"
    assert target.read_bytes() == before
    assert set(tmp_path.iterdir()) == entries
