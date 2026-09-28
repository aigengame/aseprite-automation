"""Integer rounding policies shared by native geometry and motion."""

from typing import Literal

from spa.ports import PackagedResource

Rounding = Literal["toward-zero", "floor", "ceil", "nearest-away-from-zero"]
ROUNDING_RESOURCE = PackagedResource("rounding", "rounding.lua")
