"""Export checks that more than one delivery E2E module uses."""

import hashlib
import struct
from pathlib import Path

from tests.native_invocation import expect_success


def png_icc_label(encoded: bytes) -> bytes:
    offset = 8
    while offset < len(encoded):
        size = struct.unpack_from(">I", encoded, offset)[0]
        if encoded[offset + 4 : offset + 8] == b"iCCP":
            return encoded[offset + 8 : offset + 8 + size].split(b"\0", 1)[0]
        offset += 12 + size
    raise AssertionError("PNG has no iCCP chunk")


def export_verified_image(request: dict) -> dict:
    """Run Export Image, which must succeed, and return its result.

    This also checks that the reported artifact has the path, PNG media type,
    byte size and SHA-256 of the file at the request destination.
    """
    result = expect_success("export image", request)
    destination = Path(request["destination"]["path"])
    payload = destination.read_bytes()
    assert result["artifact"] == {
        "role": "image",
        "path": str(destination),
        "media_type": "image/png",
        "format": "png",
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return result
