"""Native Slice fixtures, including Keys unavailable through public Lua setters."""

import struct
from pathlib import Path

from spa.contracts.ports import RuntimeObservation
from tests.native_invocation import run_lua
from tests.support import process_diagnostics

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(runtime: RuntimeObservation, target: Path, *, animated=True) -> None:
    """Write the Slice Sprite of `slices.lua` to target.

    When animated, also add native Slice Keys that public Lua setters cannot write.
    """
    lua = run_lua(FIXTURES / "slices.lua", runtime, target=target)
    assert lua.returncode == 0, process_diagnostics(lua)
    if not animated:
        return
    # Only fixture construction uses file-format chunks. Product mutations use
    # public native APIs and never patch Slice Keys in a file.
    data = bytearray(target.read_bytes())
    chunks = []
    for name, frames in [("multi", [0, 2, 4]), ("late", [2])]:
        encoded = name.encode()
        body = struct.pack("<IIIH", len(frames), 3, 0, len(encoded)) + encoded
        for frame in frames:
            body += struct.pack(
                "<IiiIIiiIIii", frame, -2 + frame, 3, 6, 4, 1, 1, 2, 2, -1, 5
            )
        chunks.append(struct.pack("<IH", len(body) + 6, 0x2022) + body)
    extra = b"".join(chunks)
    frame_size = struct.unpack_from("<I", data, 128)[0]
    count = struct.unpack_from("<H", data, 134)[0]
    data[128 + frame_size : 128 + frame_size] = extra
    struct.pack_into("<I", data, 0, len(data))
    struct.pack_into("<I", data, 128, frame_size + len(extra))
    struct.pack_into("<H", data, 134, count + len(chunks))
    struct.pack_into("<I", data, 140, count + len(chunks))
    target.write_bytes(data)


def mutation(source, destination, **fields):
    """Return a copy-to-target Slice mutation request with fields."""
    return dict(
        source_sprite_file=str(source),
        target_sprite_file=str(destination),
        in_place=False,
        overwrite=False,
        **fields,
    )
