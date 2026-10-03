"""Explicit Tileset intent and evidence for Tilemap Layer creation."""

from typing import Literal

from pydantic import Field, model_validator

from spa.authoring.document.sprite import LayerFacts
from spa.authoring.tile.targets import TileInspectionDetails, TilesetTarget
from spa.authoring.tile.values import TilesetFacts
from spa.contracts.ports import KernelInvocationResult, OperationIssue, PackagedResource
from spa.contracts.public import PublicModel

TILE_LAYER_RESOURCE = PackagedResource("tile_layer_creation", "tile/layer_creation.lua")
TILE_LAYER_PROBE_RESOURCE = PackagedResource(
    "tile_layer_probe", "tile/layer_creation_probe.lua"
)


class TilesetOrigin(PublicModel):
    x: int = Field(ge=0, le=0)
    y: int = Field(ge=0, le=0)


class TileSize(PublicModel):
    width: int = Field(ge=1, le=65535)
    height: int = Field(ge=1, le=65535)


class TilesetCreationGrid(PublicModel):
    origin: TilesetOrigin
    tile_size: TileSize


class TilesetCreate(PublicModel):
    name: str = Field(min_length=1, pattern=r"^[^\x00]*$")
    grid: TilesetCreationGrid
    base_index: int = Field(ge=-32768, le=32767)


class TilesetShare(PublicModel):
    tileset_index: int | None = Field(default=None, ge=1)
    tileset_name: str | None = Field(default=None, pattern=r"^[^\x00]*$")

    @model_validator(mode="after")
    def exact_address(self) -> "TilesetShare":
        TilesetTarget.model_validate(self.model_dump(exclude_none=True))
        return self


class TilesetIntent(PublicModel):
    create: TilesetCreate | None = None
    share: TilesetShare | None = None

    @model_validator(mode="after")
    def one_intent(self) -> "TilesetIntent":
        if (self.create is None) == (self.share is None):
            raise ValueError("Specify exactly one Tileset create or share intent")
        return self


class TilemapLayerCreation(PublicModel):
    intent: Literal["create", "share"]
    tileset: TilesetFacts
    before_tileset_count: int = Field(ge=0)
    tileset_count: int = Field(ge=1)
    initial_cel_count: int = Field(ge=0)
    temporary_tilesets_removed: int = Field(ge=0, le=1)
    shared_tileset_before: TilesetFacts | None


def reject_tileset(invocation: KernelInvocationResult, intent: TilesetIntent) -> None:
    rejection = invocation.payload.get("rejection")
    if not isinstance(rejection, dict) or rejection.get("code") not in (
        "tileset_missing",
        "tileset_ambiguous",
    ):
        return
    if intent.share is None or not isinstance(rejection.get("message"), str):
        raise ValueError("Tileset rejection does not match share intent")
    raise OperationIssue(
        rejection["code"],
        rejection["message"],
        TileInspectionDetails(
            target=TilesetTarget.model_validate(
                intent.share.model_dump(exclude_none=True)
            )
        ),
    )


def validate_creation(
    evidence: TilemapLayerCreation, intent: TilesetIntent, layer: LayerFacts
) -> None:
    if not layer.is_tilemap or evidence.initial_cel_count != 0:
        raise ValueError("New Tilemap Layer must have no Cels")
    bound = [item for item in evidence.tileset.layers if item.layer_path == layer.path]
    if (
        len(bound) != 1
        or bound[0].layer_uuid != layer.layer_uuid
        or bound[0].name != layer.name
        or evidence.tileset.tileset_index > evidence.tileset_count
    ):
        raise ValueError("Created Layer binding differs from reopened Layer")
    if intent.create is not None:
        expected = intent.create
        if (
            evidence.intent != "create"
            or evidence.shared_tileset_before is not None
            or evidence.tileset_count != evidence.before_tileset_count + 1
            or evidence.tileset.tileset_index != evidence.tileset_count
            or evidence.temporary_tilesets_removed != 0
            or evidence.tileset.name != expected.name
            or evidence.tileset.base_index != expected.base_index
            or evidence.tileset.grid.model_dump() != expected.grid.model_dump()
            or evidence.tileset.tile_count != 1
            or len(evidence.tileset.layers) != 1
        ):
            raise ValueError("Created Tileset differs from explicit intent")
    else:
        assert intent.share is not None
        before = evidence.shared_tileset_before
        retained_bindings = [
            item for item in evidence.tileset.layers if item.layer_path != layer.path
        ]
        if (
            before is None
            or evidence.intent != "share"
            or evidence.tileset_count != evidence.before_tileset_count
            or evidence.temporary_tilesets_removed != 1
            or (
                intent.share.tileset_index is not None
                and before.tileset_index != intent.share.tileset_index
            )
            or (
                intent.share.tileset_name is not None
                and before.name != intent.share.tileset_name
            )
            or before.model_dump(exclude={"layers"})
            != evidence.tileset.model_dump(exclude={"layers"})
            or len(retained_bindings) != len(before.layers)
            or any(
                old.model_dump(exclude={"layer_uuid"})
                != retained.model_dump(exclude={"layer_uuid"})
                # Document persistence permits native UUID assignment on save.
                # An already verified UUID must still match exactly.
                or (
                    old.layer_uuid is not None and retained.layer_uuid != old.layer_uuid
                )
                for old, retained in zip(before.layers, retained_bindings, strict=True)
            )
        ):
            raise ValueError("Shared Tileset or existing bindings differ from intent")
