"""Compare independently decoded files with native pre-layout observations."""

import json
import re
from typing import Any, Literal

from pydantic import Field

from spa.authoring.color.profile import supported_icc_identity
from spa.authoring.raster.image_snapshot import LayerComposition
from spa.contracts.ports import PngInputFacts
from spa.contracts.public import PublicModel
from spa.delivery.sheet_contracts import (
    ExportSheetRequest,
    SheetFrame,
    SheetRange,
    SheetRect,
    SheetTagFacts,
)


class NativeSheetFrame(PublicModel):
    frame_number: int = Field(ge=1)
    duration_ms: int = Field(ge=1)
    trim: SheetRect
    pixels_offset: int = Field(ge=0)
    pixels_byte_size: int = Field(gt=0)


class NativeSheet(PublicModel):
    width: int = Field(gt=0, le=65535)
    height: int = Field(gt=0, le=65535)
    source_width: int = Field(gt=0, le=65535)
    source_height: int = Field(gt=0, le=65535)
    color_mode: Literal["rgb", "indexed"]
    color_profile: Literal["none", "srgb", "icc"]
    icc_identity: Literal["linear_srgb", "display_p3"] | None = None
    transparent_index: int | None = Field(default=None, ge=0, le=255)
    palette: list[list[int]] | None = None
    source_frames: list[int] = Field(min_length=1)
    frames: list[NativeSheetFrame] = Field(min_length=1)
    source_tags: list[SheetTagFacts]
    projected_tags: list[dict[str, Any]]
    selected_tag: SheetTagFacts | None = None
    common_trim: SheetRect | None = None
    effective_background: bool
    layer_composition: LayerComposition
    resolved_layer_paths: list[list[int]]
    rendered_byte_size: int = Field(gt=0)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _rect(value: Any) -> SheetRect:
    _require(
        isinstance(value, dict) and set(value) == {"x", "y", "w", "h"},
        "Invalid frame rectangle",
    )
    return SheetRect(x=value["x"], y=value["y"], width=value["w"], height=value["h"])


def _projected_tags(native: NativeSheet) -> list[dict[str, Any]]:
    first, last = native.source_frames[0], native.source_frames[-1]
    directions = {"ping_pong": "pingpong", "ping_pong_reverse": "pingpong_reverse"}
    result = []
    for tag in native.source_tags:
        if tag.from_frame < first or tag.to_frame > last:
            continue
        color = tag.color
        projected = {
            "name": tag.name,
            "from": tag.from_frame - first,
            "to": tag.to_frame - first,
            "direction": directions.get(tag.direction, tag.direction),
            "color": f"#{color.red:02x}{color.green:02x}{color.blue:02x}{color.alpha:02x}",
        }
        if tag.repeats:
            projected["repeat"] = str(tag.repeats)
        result.append(projected)
    return result


def verify_sheet(
    request: ExportSheetRequest,
    native: NativeSheet,
    png: PngInputFacts,
    metadata_bytes: bytes,
    pixels: bytes,
    image_reference: str,
) -> list[SheetFrame]:
    """Verify each logical record; physical rectangle sharing is permitted."""
    metadata = json.loads(metadata_bytes, object_pairs_hook=_object)
    _require(isinstance(metadata, dict), "JSON metadata must be an object")
    records, meta = metadata["frames"], metadata["meta"]
    _require(
        isinstance(records, list) and isinstance(meta, dict),
        "Expected JSON Array metadata",
    )
    _require(
        len(records) == len(native.frames) == len(native.source_frames),
        "Logical Frame count differs",
    )
    _require(
        png.color_mode == native.color_mode == request.output_color_mode,
        "Color Mode differs",
    )
    _require(
        (png.width, png.height) == (native.width, native.height),
        "Atlas dimensions differ",
    )
    _require(
        meta["size"] == {"w": png.width, "h": png.height},
        "Metadata texture size differs",
    )
    _require(
        meta["image"] == image_reference and meta["scale"] == "1",
        "Metadata image reference or scale differs",
    )
    _require(
        meta["format"] == ("I8" if png.color_mode == "indexed" else "RGBA8888"),
        "Metadata pixel encoding differs",
    )
    _require(png.color_profile == native.color_profile, "Color Profile differs")
    if png.color_profile == "icc":
        _require(
            png.icc_bytes is not None
            and supported_icc_identity(png.icc_bytes) == native.icc_identity,
            "ICC payload differs",
        )
    elif png.color_profile == "srgb":
        _require(png.srgb_rendering_intent == 0, "Native sRGB rendering intent differs")
    _require(
        native.layer_composition == request.layer_composition,
        "Layer Composition differs",
    )
    if isinstance(request.selection, SheetRange):
        first, last = request.selection.from_frame, request.selection.to_frame
        _require(native.selected_tag is None, "Unexpected selected Tag")
    else:
        tag = native.selected_tag
        _require(
            tag is not None and tag in native.source_tags, "Missing selected Source Tag"
        )
        assert tag is not None
        address = request.selection.tag
        _require(
            (address.tag_index is None or address.tag_index == tag.tag_index)
            and (address.tag_name is None or address.tag_name == tag.name),
            "Selected Tag address differs",
        )
        first, last = tag.from_frame, tag.to_frame
    _require(
        native.source_frames == list(range(first, last + 1)),
        "Source Frame order differs",
    )
    _require(
        meta.get("frameTags", []) == _projected_tags(native), "Tag projection differs"
    )
    bpp = 1 if png.color_mode == "indexed" else 4
    frame_bytes = native.source_width * native.source_height * bpp
    _require(
        len(pixels) == native.rendered_byte_size == frame_bytes * len(records),
        "Native sample byte count differs",
    )
    if png.color_mode == "indexed":
        _require(
            native.palette is not None and native.transparent_index is not None,
            "Missing Indexed palette context",
        )
        assert native.palette is not None and native.transparent_index is not None
        entries = [tuple(color) for color in native.palette]
        _require(
            1 <= len(entries) <= 256 and native.transparent_index < len(entries),
            "Invalid palette size or transparent index",
        )
        color = entries[native.transparent_index]
        entries[native.transparent_index] = (*color[:3], 0)
        _require(tuple(entries) == png.entries, "Full ordered Palette differs")
        background = bytes([native.transparent_index])
    else:
        background = bytes(4)
    expected = bytearray(background * (png.width * png.height))
    result = []
    token = re.search(r"\{frame(0*[01])\}", request.filename_format)
    assert token is not None
    padding = request.padding
    for ordinal, (record, sample, source_frame) in enumerate(
        zip(records, native.frames, native.source_frames, strict=True)
    ):
        _require(isinstance(record, dict), "Frame record must be an object")
        rect, trim = _rect(record["frame"]), _rect(record["spriteSourceSize"])
        _require(
            sample.frame_number == source_frame
            and sample.pixels_offset == ordinal * frame_bytes
            and sample.pixels_byte_size == frame_bytes,
            "Native Frame association differs",
        )
        _require(trim == sample.trim, "Trim rectangle differs from native observation")
        _require(
            record["sourceSize"]
            == {"w": native.source_width, "h": native.source_height},
            "Original Canvas size differs",
        )
        _require(
            record["rotated"] is False, "Rotated sheet frames are outside this contract"
        )
        _require(
            type(record["duration"]) is int
            and record["duration"] == sample.duration_ms,
            "Frame duration differs",
        )
        number = str(ordinal + int(token.group(1))).zfill(len(token.group(1)))
        expected_name = (
            request.filename_format[: token.start()]
            + number
            + request.filename_format[token.end() :]
        )
        _require(
            record["filename"] == expected_name,
            "Frame name differs from declared output ordinal",
        )
        _require(
            (rect.width, rect.height)
            == (trim.width + 2 * padding.inner, trim.height + 2 * padding.inner),
            "Inner padding dimensions differ",
        )
        _require(
            rect.x >= padding.border
            and rect.y >= padding.border
            and rect.x + rect.width + padding.border <= png.width
            and rect.y + rect.height + padding.border <= png.height,
            "Frame rectangle exceeds texture or border",
        )
        _require(
            trim.x + trim.width <= native.source_width
            and trim.y + trim.height <= native.source_height,
            "Trim exceeds Source Canvas",
        )
        for row in range(trim.height):
            source = (
                sample.pixels_offset
                + ((trim.y + row) * native.source_width + trim.x) * bpp
            )
            target = (
                (rect.y + padding.inner + row) * png.width + rect.x + padding.inner
            ) * bpp
            expected[target : target + trim.width * bpp] = pixels[
                source : source + trim.width * bpp
            ]
        result.append(
            SheetFrame(
                source_frame=source_frame,
                filename=record["filename"],
                duration_ms=sample.duration_ms,
                rectangle=rect,
                source_rectangle=trim,
                source_width=native.source_width,
                source_height=native.source_height,
            )
        )
    _require(
        expected == png.stored_bytes,
        "Atlas pixels or padding differ from native samples",
    )
    return result
