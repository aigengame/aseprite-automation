"""Shared explicit destination for complete JSON Snapshot transport."""

from typing import Literal

from pydantic import Field

from spa.contracts.public import PublicModel


class SnapshotDestination(PublicModel):
    path: str = Field(
        min_length=6,
        pattern=r"^[^\x00\r\n]+\.json$",
        json_schema_extra={"not": {"pattern": r"[\r\n]"}},
    )
    if_exists: Literal["fail", "replace"]
