"""Independent decoding of the staged PNG Artifact."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

from PIL import Image, UnidentifiedImageError

from spa.ports import ArtifactVerificationEvidence, RuntimeIssue


@dataclass(frozen=True)
class PngFacts:
    width: int
    height: int
    color_profile: Literal["none", "srgb"]
    alpha_channel_present: bool
    alpha_min: int
    alpha_max: int
    content_digest: str


def _fnv1a64(data: bytes) -> str:
    value = 0xCBF29CE484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


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
                content_digest=_fnv1a64(rgba.tobytes()),
            )
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise RuntimeIssue(
            "artifact_verification_failed",
            f"Staged PNG did not pass independent decoding: {exc}",
            ArtifactVerificationEvidence(str(staged), str(exc)),
        ) from exc
