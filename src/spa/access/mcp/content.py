"""Present CLI outcomes and verified PNG Artifacts without changing their facts."""

import base64
import hashlib
import io
import json
import os
import stat
from typing import Any

from jsonschema import Draft202012Validator, ValidationError
from mcp.types import CallToolResult, ImageContent, TextContent
from PIL import Image

from spa.access.mcp.cli import AdapterError, Outcome


def adapter_failure(error: AdapterError) -> CallToolResult:
    return CallToolResult(
        is_error=True,
        content=[
            TextContent(
                type="text", text=json.dumps({"adapter_error": error.diagnostics})
            )
        ],
    )


def _png_content(artifact: dict[str, Any]) -> ImageContent:
    path = artifact["path"]
    # Nonblocking open lets a replaced pipe/device fail as a non-file, not hang.
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        facts = os.fstat(source.fileno())
        if not stat.S_ISREG(facts.st_mode) or facts.st_size != artifact["byte_size"]:
            raise ValueError("Artifact is not a regular file of the reported size")
        data = source.read(artifact["byte_size"] + 1)
    if (
        len(data) != artifact["byte_size"]
        or hashlib.sha256(data).hexdigest() != artifact["sha256"]
    ):
        raise ValueError("PNG bytes differ from the reported Artifact")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG":
            raise ValueError("Artifact bytes are not PNG")
        image.verify()
    return ImageContent(
        type="image", mime_type="image/png", data=base64.b64encode(data).decode("ascii")
    )


def project_outcome(outcome: Outcome, entry: dict[str, Any]) -> CallToolResult:
    success = outcome.exit_status == 0
    schema = entry["result_schema" if success else "failure_schema"]
    try:
        Draft202012Validator(schema).validate(outcome.payload)
    except ValidationError as exc:
        raise AdapterError(
            "SPA output does not match its published schema",
            reason=exc.message,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            exit_status=outcome.exit_status,
        ) from exc
    result = CallToolResult(
        is_error=not success,
        structured_content=outcome.payload if success else None,
        content=[TextContent(type="text", text=outcome.stdout)],
    )
    if not success:
        return result
    # Public Results declare singular/plural Artifact fields. Never walk arbitrary
    # nested JSON such as caller-owned script output, snapshots or schema data.
    properties = schema.get("properties", {})
    artifacts = []
    if "artifact" in properties and outcome.payload.get("artifact"):
        artifacts.append(outcome.payload["artifact"])
    if "artifacts" in properties:
        artifacts.extend(outcome.payload.get("artifacts", []))
    for artifact in artifacts:
        if artifact.get("media_type") != "image/png":
            continue
        try:
            result.content.append(_png_content(artifact))
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            result.is_error = True
            result.content.append(
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "adapter_error": {
                                "phase": "content_projection",
                                "path": artifact["path"],
                                "message": str(exc),
                                "operation_completed": True,
                            },
                        }
                    ),
                )
            )
    return result
