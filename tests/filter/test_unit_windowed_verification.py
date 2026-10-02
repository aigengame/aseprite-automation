"""Aggregate report lifecycle with synthetic receipts and native observations.

These checks exercise retained evidence, not real windowed Aseprite interactions.
"""

import hashlib
import json
from pathlib import Path

import pytest

from tests.filter import windowed


@pytest.fixture
def comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cases = []
    for name in windowed.CASES:
        folder = tmp_path / name
        folder.mkdir()
        source = folder / "source.aseprite"
        source.write_bytes(b"original Source")
        target = folder / "ui.aseprite"
        target.write_text(json.dumps({"pixels": [120]}))
        (folder / "expected.json").write_text(target.read_text())
        receipt = folder / "ui-receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "name": name,
                    "version": "synthetic",
                    "is_ui_available": True,
                    "reopened": True,
                    "tileset_mode": "manual",
                    "active_frame": 1,
                    "frames": [1],
                    "colors": [],
                    "selection_pixels": 3,
                }
            )
        )
        cases.append(
            {
                "name": name,
                "mode": "rgb",
                "source": str(source),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "target": str(target),
                "receipt": str(receipt),
                "basis": 1,
                "frames": [1],
                "palette": False,
                "selection": {"rectangle": {"width": 3}},
            }
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"source_head": "synthetic", "cases": cases})
    )
    # Replace only the external native observation with controlled persisted data.
    monkeypatch.setattr(
        windowed,
        "observation",
        lambda runtime, path, mode: json.loads(path.read_text()),
    )
    return tmp_path


@pytest.mark.parametrize("failure", ["missing_receipt", "differing_output"])
def test_failed_reverification_removes_previous_success(
    comparison: Path, failure: str
) -> None:
    windowed.verify(comparison, runtime=None)
    report = comparison / "comparison.json"
    prior = json.loads(report.read_text())
    assert len(prior["cases"]) == 7
    assert all(case["matches_spa"] for case in prior["cases"])

    if failure == "missing_receipt":
        (comparison / "rgb/ui-receipt.json").unlink()
        error = FileNotFoundError
    else:
        (comparison / "rgb/ui.aseprite").write_text(json.dumps({"pixels": [80]}))
        error = AssertionError

    with pytest.raises(error):
        windowed.verify(comparison, runtime=None)

    assert not report.exists(), "Failed verification retained a complete success report"
