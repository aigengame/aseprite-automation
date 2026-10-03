"""Native Slice fixtures, including Keys unavailable through public Lua setters."""

import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

from spa.adapters.aseprite.invocation import prepare_invocation
from tests.support import process_diagnostics, spa


def run(*command, **request):
    result = spa(
        *command,
        "--input-json",
        json.dumps({**request, "aseprite": os.environ["SPA_TEST_ASEPRITE"]}),
    )
    assert result.stdout, process_diagnostics(result)
    return result.returncode, json.loads(result.stdout)


def native_script(script, **params):
    executable = Path(os.environ["SPA_TEST_ASEPRITE"])
    with tempfile.TemporaryDirectory(prefix="spa-slice-fixture-") as work:
        prepared = prepare_invocation(
            executable, executable.parent.parent / "Resources/data/gui.xml", Path(work)
        )
        args = [str(prepared.executable), "--batch"]
        for name, value in params.items():
            args.extend(["--script-param", f"{name}={value}"])
        result = subprocess.run(
            [*args, "--script", str(Path(__file__).parent / "fixtures" / script)],
            env=prepared.environment,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 0, process_diagnostics(result)


def fixture(target, *, animated=True):
    native_script("slices.lua", target=target)
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
    return dict(
        source_sprite_file=str(source),
        target_sprite_file=str(destination),
        in_place=False,
        overwrite=False,
        **fields,
    )
