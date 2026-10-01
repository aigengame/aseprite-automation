"""Validate ICC file structure and observe bytes without transforming colors."""

import hashlib
from io import BytesIO

from PIL import ImageCms

from spa.contracts.ports import IccFacts, IccVerificationError


def verify_icc(payload: bytes) -> IccFacts:
    try:
        ImageCms.ImageCmsProfile(BytesIO(payload))
    except (OSError, ValueError, TypeError) as exc:
        raise IccVerificationError("Invalid ICC profile") from exc
    return IccFacts(
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        color_space=payload[16:20].decode("ascii", errors="replace").strip(),
    )
