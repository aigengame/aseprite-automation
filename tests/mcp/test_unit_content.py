"""Content projection preserves CLI facts even if a published file changes."""

import base64
import hashlib
import json

import pytest
from PIL import Image

from spa.access.mcp.cli import Outcome
from spa.access.mcp.content import project_outcome


@pytest.fixture
def publication(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGBA", (2, 1), (17, 34, 51, 128)).save(path)
    data = path.read_bytes()
    artifact = {
        "role": "image",
        "path": str(path),
        "media_type": "image/png",
        "format": "png",
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    payload = {"status": "success", "operation": "spa example", "artifact": artifact}
    outcome = Outcome(payload, json.dumps(payload), "", 0)
    entry = {
        "result_schema": {
            "type": "object",
            "properties": {"artifact": {"type": "object"}},
        }
    }
    return path, data, outcome, entry


def test_png_is_additional_content_and_result_is_unchanged(publication):
    _, data, outcome, entry = publication
    result = project_outcome(outcome, entry)
    assert not result.is_error
    assert result.structured_content == outcome.payload
    assert json.loads(result.content[0].text) == outcome.payload
    assert base64.b64decode(result.content[1].data, validate=True) == data


@pytest.mark.parametrize("change", ["missing", "size", "digest", "not-png"])
def test_projection_failure_does_not_relabel_completed_operation(publication, change):
    path, data, outcome, entry = publication
    if change == "missing":
        path.unlink()
    elif change == "size":
        path.write_bytes(data + b"changed")
    elif change == "digest":
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    else:
        path.write_bytes(b"x" * len(data))
        outcome.payload["artifact"]["sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    outcome = Outcome(outcome.payload, json.dumps(outcome.payload), "", 0)
    result = project_outcome(outcome, entry)
    assert result.is_error
    assert result.structured_content == outcome.payload
    assert json.loads(result.content[0].text) == outcome.payload
    assert not any(part.type == "image" for part in result.content)
    error = json.loads(result.content[1].text)["adapter_error"]
    assert error["phase"] == "content_projection"
    assert error["operation_completed"] is True
    assert error["path"] == str(path)


def test_plural_artifacts_keep_non_png_metadata_without_opening_them(publication):
    _, data, outcome, _ = publication
    payload = {
        "artifacts": [
            outcome.payload["artifact"],
            {"media_type": "image/gif", "path": "/does-not-exist.gif"},
        ]
    }
    result = project_outcome(
        Outcome(payload, json.dumps(payload), "", 0),
        {"result_schema": {"properties": {"artifacts": {"type": "array"}}}},
    )
    assert not result.is_error
    assert result.structured_content == payload
    assert len(result.content) == 2
    assert base64.b64decode(result.content[1].data) == data


def test_artifact_shaped_caller_json_is_not_a_file_read(publication):
    path, _, outcome, _ = publication
    path.unlink()
    payload = {
        "caller_output": outcome.payload,
        "artifact": outcome.payload["artifact"],
    }
    result = project_outcome(
        Outcome(payload, json.dumps(payload), "", 0),
        {"result_schema": {"type": "object"}},
    )
    assert not result.is_error
    assert len(result.content) == 1
