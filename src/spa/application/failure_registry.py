"""Immutable composition of installed public Failure Code semantics."""

from spa.authoring.color.color_mode import COLOR_MODE_FAILURE_SPECS
from spa.authoring.color.palette import PALETTE_FAILURE_CODE_SPECS
from spa.authoring.color.profile import PROFILE_FAILURE_SPECS
from spa.authoring.document.animation import ANIMATION_FAILURE_CODE_SPECS
from spa.authoring.document.cel import CEL_FAILURE_CODE_SPECS
from spa.authoring.document.layer import LAYER_FAILURE_CODE_SPECS
from spa.authoring.document.motion import MOTION_FAILURE_CODE_SPECS
from spa.authoring.document.sprite import SPRITE_FAILURE_CODE_SPECS
from spa.authoring.document.tag import TAG_FAILURE_CODE_SPECS
from spa.authoring.raster.image import (
    IMAGE_CANVAS_FAILURE_CODE_SPECS,
    IMAGE_RESIZE_FAILURE_CODE_SPECS,
    IMAGE_ROTATE_FAILURE_CODE_SPECS,
)
from spa.authoring.raster.image_snapshot import IMAGE_SNAPSHOT_FAILURE_CODE_SPECS
from spa.authoring.raster.paint_composite import COMPOSITE_FAILURE_CODE_SPECS
from spa.authoring.raster.paint_native import NATIVE_PAINT_FAILURE_CODE_SPECS
from spa.authoring.raster.selection import SELECTION_FAILURE_CODE_SPECS
from spa.contracts.mutation import MUTATION_FAILURE_CODE_SPECS
from spa.contracts.public import CORE_FAILURE_CODE_SPECS, register_failure_codes
from spa.delivery.export import EXPORT_FAILURE_CODE_SPECS

FAILURE_CODES = register_failure_codes(
    (
        *CORE_FAILURE_CODE_SPECS,
        *PALETTE_FAILURE_CODE_SPECS,
        *COLOR_MODE_FAILURE_SPECS,
        *PROFILE_FAILURE_SPECS,
        *ANIMATION_FAILURE_CODE_SPECS,
        *CEL_FAILURE_CODE_SPECS,
        *MUTATION_FAILURE_CODE_SPECS,
        *COMPOSITE_FAILURE_CODE_SPECS,
        *MOTION_FAILURE_CODE_SPECS,
        *NATIVE_PAINT_FAILURE_CODE_SPECS,
        *SELECTION_FAILURE_CODE_SPECS,
        *EXPORT_FAILURE_CODE_SPECS,
        *IMAGE_RESIZE_FAILURE_CODE_SPECS,
        *IMAGE_SNAPSHOT_FAILURE_CODE_SPECS,
        *IMAGE_CANVAS_FAILURE_CODE_SPECS,
        *IMAGE_ROTATE_FAILURE_CODE_SPECS,
        *LAYER_FAILURE_CODE_SPECS,
        *SPRITE_FAILURE_CODE_SPECS,
        *TAG_FAILURE_CODE_SPECS,
    )
)
