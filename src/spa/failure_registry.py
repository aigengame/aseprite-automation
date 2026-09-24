"""Immutable composition of installed public Failure Code semantics."""

from spa.cel import CEL_FAILURE_CODE_SPECS
from spa.contracts import CORE_FAILURE_CODE_SPECS, register_failure_codes
from spa.export import EXPORT_FAILURE_CODE_SPECS
from spa.layer import LAYER_FAILURE_CODE_SPECS
from spa.mutation import MUTATION_FAILURE_CODE_SPECS
from spa.sprite import SPRITE_FAILURE_CODE_SPECS
from spa.tag import TAG_FAILURE_CODE_SPECS

FAILURE_CODES = register_failure_codes(
    (
        *CORE_FAILURE_CODE_SPECS,
        *CEL_FAILURE_CODE_SPECS,
        *MUTATION_FAILURE_CODE_SPECS,
        *EXPORT_FAILURE_CODE_SPECS,
        *LAYER_FAILURE_CODE_SPECS,
        *SPRITE_FAILURE_CODE_SPECS,
        *TAG_FAILURE_CODE_SPECS,
    )
)
