"""Immutable composition of installed public Failure Code semantics."""

from spa.contracts import CORE_FAILURE_CODE_SPECS, register_failure_codes
from spa.export import EXPORT_FAILURE_CODE_SPECS
from spa.sprite import SPRITE_FAILURE_CODE_SPECS

FAILURE_CODES = register_failure_codes(
    (*CORE_FAILURE_CODE_SPECS, *SPRITE_FAILURE_CODE_SPECS, *EXPORT_FAILURE_CODE_SPECS)
)
