"""Shared native Image evidence digest binding."""

from spa.contracts.ports import PackagedResource

DIGEST_RESOURCE = PackagedResource("digest", "foundation/digest.lua")


def fnv1a64(payload: bytes) -> str:
    """Compare independently decoded bytes with the native evidence algorithm."""
    value = 14695981039346656037
    for byte in payload:
        value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"
