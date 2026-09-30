"""Independent decoding of the staged PNG Artifact."""

from io import BytesIO
from pathlib import Path
from typing import Literal, cast

from PIL import Image, UnidentifiedImageError

from spa.contracts.ports import ArtifactVerificationEvidence, PngFacts, RuntimeIssue


def verify_png(payload: bytes, staged: Path) -> PngFacts:
    try:
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("PNG signature is absent")
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG":
                raise ValueError("Decoded file is not PNG")
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                raise ValueError(
                    f"PNG has unsupported channel representation: {image.mode}"
                )
            if "icc_profile" in image.info:
                raise ValueError("PNG contains an unsupported ICC Profile")
            if "srgb" in image.info:
                profile: Literal["none", "srgb"] = "srgb"
            elif "gamma" in image.info or "chromaticity" in image.info:
                raise ValueError("PNG contains an unsupported Color Profile encoding")
            else:
                profile = "none"
            rgba = image.convert("RGBA")
            alpha_min, alpha_max = cast(
                tuple[int, int], rgba.getchannel("A").getextrema()
            )
            return PngFacts(
                width=image.width,
                height=image.height,
                color_profile=profile,
                alpha_channel_present=image.mode == "RGBA",
                alpha_min=alpha_min,
                alpha_max=alpha_max,
                rgba_bytes=rgba.tobytes(),
            )
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise RuntimeIssue(
            "artifact_verification_failed",
            f"Staged PNG did not pass independent decoding: {exc}",
            ArtifactVerificationEvidence(str(staged), str(exc)),
        ) from exc
