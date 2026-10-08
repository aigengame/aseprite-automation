"""Verified native Tileset atlas and normalized map export."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from spa.authoring.color.profile import PROFILE_RESOURCES, supported_icc_identity
from spa.authoring.document.targets import (
    LAYER_FAILURE_CODE_SPECS,
    LayerAddress,
    LayerTargetDetails,
)
from spa.authoring.tile.inspection import TILE_READ_HANDLER
from spa.authoring.tile.targets import TILE_FAILURE_SPECS, TileInspectionDetails
from spa.contracts.digest import fnv1a64
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import (
    ArtifactPublication,
    ArtifactVerificationEvidence,
    KernelInvocationResult,
    OperationIssue,
    OperationServices,
    PackagedHandler,
    PackagedResource,
    PngRasterFacts,
    ResponseEvidence,
    RuntimeIssue,
)
from spa.contracts.public import FailureCodeSpec, PublicModel, RuntimeRequirements
from spa.contracts.snapshot import SnapshotDestination
from spa.delivery.export import EXPORT_SUPPORT, ExportDestination
from spa.delivery.tileset_contracts import (
    ExportTilesetRequest,
    ExportTilesetResult,
    NativeTilesetExport,
    TilesetArtifact,
    TilesetMap,
)


class TilesetExportDetails(PublicModel):
    kind: Literal["tileset_export"] = "tileset_export"
    reason: str = Field(min_length=1)


TILESET_EXPORT_FAILURE_SPECS = (
    FailureCodeSpec(
        "tileset_export_unsupported",
        "The selected Tileset cannot satisfy the explicit atlas and map contract",
        "input",
        TilesetExportDetails,
    ),
)

TILESET_EXPORT_HANDLER = PackagedHandler(
    "export_tileset",
    "delivery/export_tileset.lua",
    tuple(
        dict.fromkeys(
            (
                *TILE_READ_HANDLER.support_resources,
                *PROFILE_RESOURCES,
                EXPORT_SUPPORT,
                PackagedResource(
                    "export_tileset_support", "delivery/export_tileset_support.lua"
                ),
            )
        )
    ),
)
TILESET_EXPORT_REQUIREMENTS = RuntimeRequirements(
    lua_language="Lua 5.4",
    minimum_api_version=41,
    required_capabilities=["aseprite_tile_inspection", "aseprite_export_image"],
)


def _native(
    invocation: KernelInvocationResult, request: ExportTilesetRequest
) -> NativeTilesetExport:
    try:
        rejection = invocation.payload.get("rejection")
        if rejection is not None:
            if not isinstance(rejection, dict) or not isinstance(
                rejection.get("message"), str
            ):
                raise ValueError("Malformed export refusal")
            code, message = rejection.get("code"), rejection["message"]
            if code == "tileset_export_unsupported":
                raise OperationIssue(
                    code, message, TilesetExportDetails(reason=rejection["reason"])
                )
            if code in {spec.code for spec in TILE_FAILURE_SPECS}:
                raise OperationIssue(
                    code,
                    message,
                    TileInspectionDetails(
                        target=request.target,
                        rectangle=request.rectangle,
                    ),
                )
            if code in {spec.code for spec in LAYER_FAILURE_CODE_SPECS}:
                raise OperationIssue(
                    code,
                    message,
                    LayerTargetDetails(
                        address_role="target", address=request.target.layer
                    ),
                )
            raise ValueError("Unknown export refusal")
        return NativeTilesetExport.model_validate(invocation.payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeIssue(
            "response_malformed",
            f"Invalid Tileset export evidence: {exc}",
            ResponseEvidence(invocation.response_path),
            invocation.diagnostics,
        ) from exc


def _matches_layer(address: LayerAddress, layer) -> bool:
    return (
        (address.layer_path is None or address.layer_path == layer.layer_path)
        and (address.layer_name is None or address.layer_name == layer.name)
        and (address.layer_uuid is None or address.layer_uuid == layer.layer_uuid)
    )


def _check_request(
    request: ExportTilesetRequest, value: TilesetMap, source: Path, image: Path
) -> None:
    if (
        value.source_sprite_file != str(source)
        or value.atlas.path != str(image)
        or value.atlas.columns != request.columns
        or value.tilemap.frame_number != request.target.frame_number
        or not _matches_layer(request.target.layer, value.tilemap.layer)
        or value.snapshot.rectangle != request.rectangle
    ):
        raise ValueError(
            "Export target, destinations, or complete region differ from request"
        )
    target = request.tileset
    if (
        (
            target.tileset_index is not None
            and target.tileset_index != value.tileset.tileset_index
        )
        or (
            target.tileset_name is not None
            and target.tileset_name != value.tileset.name
        )
        or (
            target.layer is not None
            and not any(
                _matches_layer(target.layer, layer) for layer in value.tileset.layers
            )
        )
    ):
        raise ValueError("Exported Tileset differs from explicit address")


def _verify_pixels(decoded: PngRasterFacts, native: NativeTilesetExport) -> None:
    atlas = native.metadata.atlas
    if (
        (decoded.width, decoded.height) != (atlas.width, atlas.height)
        or decoded.color_mode != atlas.color_mode
        or decoded.color_type != atlas.png.color_type
        or decoded.color_profile != atlas.profile.kind
        or (decoded.color_profile == "srgb" and decoded.srgb_rendering_intent != 0)
        or (
            decoded.icc_bytes is not None
            and supported_icc_identity(decoded.icc_bytes) != atlas.profile.icc_identity
        )
    ):
        raise ValueError("Decoded PNG dimensions, encoding, or Profile differ")
    if atlas.palette is not None:
        entries = tuple(
            (c.red, c.green, c.blue, c.alpha) for c in atlas.palette.entries
        )
        if decoded.entries != entries:
            raise ValueError(
                "PNG Palette entries, order, or native transparency differ"
            )
    elif decoded.entries:
        raise ValueError("Non-Indexed PNG has unexpected Palette facts")
    channels = {"rgb": 4, "grayscale": 2, "indexed": 1}[atlas.color_mode]
    if len(decoded.stored_bytes) != atlas.width * atlas.height * channels:
        raise ValueError("Decoded PNG pixel coverage is incomplete")
    if len(native.tile_digests) != len(atlas.tiles):
        raise ValueError("Native Tile Image evidence is incomplete")
    stride = atlas.width * channels
    for tile, expected in zip(atlas.tiles, native.tile_digests):
        area = tile.rectangle
        content = b"".join(
            decoded.stored_bytes[
                y * stride + area.x * channels : y * stride
                + (area.x + area.width) * channels
            ]
            for y in range(area.y, area.y + area.height)
        )
        if fnv1a64(content) != expected:
            raise ValueError(
                f"Atlas Tile {tile.tile_index} differs from its source Tile Image"
            )
    # The only unoccupied cells are the tail of the last row; they are not Tiles.
    count = len(atlas.tiles)
    if count % atlas.columns:
        grid = native.metadata.tileset.grid.tile_size
        start_x = (count % atlas.columns) * grid.width
        start_y = (count // atlas.columns) * grid.height
        empty = (
            bytes([atlas.palette.transparent_color_index])
            if atlas.palette
            else bytes(channels)
        )
        for y in range(start_y, atlas.height):
            actual = decoded.stored_bytes[
                y * stride + start_x * channels : (y + 1) * stride
            ]
            if actual != empty * (atlas.width - start_x):
                raise ValueError("Unused final-row atlas cells must be transparent")


def _parse_map(payload: bytes) -> TilesetMap:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate map JSON field")
            result[key] = value
        return result

    return TilesetMap.model_validate(json.loads(payload, object_pairs_hook=unique))


def export_tileset(
    request: ExportTilesetRequest, services: OperationServices
) -> ExportTilesetResult:
    files, decode = services.artifact_files, services.decode_png_artifact
    if files is None or decode is None:
        raise RuntimeError("Tileset export requires Artifact files and PNG decoding")
    source = files.normalize_destination(request.source_sprite_file)
    image = files.normalize_destination(request.image.path)
    metadata = files.normalize_destination(request.metadata.path)
    files.ensure_destinations_distinct((image, metadata))
    for destination in (image, metadata):
        files.ensure_source_separate(source, destination)
    staged = []
    partial = False
    try:
        image_file = files.staged_path(image, if_exists=request.image.if_exists)
        staged.append(image_file)
        metadata_file = files.staged_path(
            metadata, if_exists=request.metadata.if_exists
        )
        staged.append(metadata_file)
        invocation = services.invoke_kernel(
            services.probe_runtime(request),
            TILESET_EXPORT_HANDLER,
            {
                "source_sprite_file": str(source),
                "tileset": request.tileset.model_dump(exclude_none=True),
                "target": request.target.model_dump(exclude_none=True),
                "rectangle": request.rectangle.model_dump(),
                "columns": request.columns,
                "image_path": str(image),
                "staged_png_file": str(image_file),
                "staged_metadata_file": str(metadata_file),
            },
            request.timeout_seconds,
        )
        native = _native(invocation, request)
        image_contents = files.read_staged(image_file)
        metadata_contents = files.read_staged(metadata_file)
        try:
            value = _parse_map(metadata_contents.payload)
            if value != native.metadata:
                raise ValueError(
                    "Staged map differs from the native target observations"
                )
            _check_request(request, value, source, image)
            _verify_pixels(decode(image_contents.payload), native)
        except (ValueError, TypeError, KeyError) as exc:
            raise RuntimeIssue(
                "artifact_verification_failed",
                f"Tileset output verification failed: {exc}",
                ArtifactVerificationEvidence(str(metadata_file), str(exc)),
                invocation.diagnostics,
            ) from exc
        for destination in (image, metadata):
            files.ensure_source_separate(source, destination)
        published = files.publish_many(
            (
                ArtifactPublication(
                    "tileset-image",
                    image_file,
                    image,
                    request.image.if_exists,
                    image_contents.sha256,
                ),
                ArtifactPublication(
                    "map-data",
                    metadata_file,
                    metadata,
                    request.metadata.if_exists,
                    metadata_contents.sha256,
                ),
            )
        )
        return ExportTilesetResult(
            image=ExportDestination(path=str(image), if_exists=request.image.if_exists),
            metadata=SnapshotDestination(
                path=str(metadata), if_exists=request.metadata.if_exists
            ),
            map=value,
            artifacts=[
                TilesetArtifact(
                    role="tileset-image",
                    path=published[0].path,
                    media_type="image/png",
                    format="png",
                    byte_size=published[0].byte_size,
                    sha256=published[0].sha256,
                ),
                TilesetArtifact(
                    role="map-data",
                    path=published[1].path,
                    media_type="application/json",
                    format="json",
                    byte_size=published[1].byte_size,
                    sha256=published[1].sha256,
                ),
            ],
        )
    except RuntimeIssue as exc:
        partial = exc.kind == "partial_publication"
        raise
    finally:
        if not partial:
            for item in staged:
                files.discard(item)


TILESET_EXPORT_OPERATIONS = (
    OperationDescriptor(
        "export tileset",
        ExportTilesetRequest,
        ExportTilesetResult,
        export_tileset,
        lambda result: result.image.path,
        TILESET_EXPORT_REQUIREMENTS,
        (
            *RUNTIME_FAILURE_CODES,
            *(spec.code for spec in TILE_FAILURE_SPECS),
            *(spec.code for spec in LAYER_FAILURE_CODE_SPECS),
            "tileset_export_unsupported",
            "artifact_file_failed",
            "artifact_verification_failed",
            "partial_publication",
        ),
        execution_kind="export",
        side_effects=("publishes a verified Tileset PNG and normalized map JSON pair",),
    ),
)
