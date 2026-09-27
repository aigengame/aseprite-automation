"""Helpers shared across test ownership areas."""

import shlex
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

from spa.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    RuntimeObservation,
    RuntimeProbe,
    TargetCommitObservation,
)


class _UnusedTargetFiles:
    def staged_path(self, _target: Path) -> Path:
        raise AssertionError("test did not configure Target Files")

    def commit(
        self, _staged: Path, _target: Path, *, overwrite: bool
    ) -> TargetCommitObservation:
        raise AssertionError("test did not configure Target Files")

    def discard(self, _staged: Path) -> None:
        return None


def operation_services(probe: RuntimeProbe) -> OperationServices:
    """Supply explicit unused adapters to tests that exercise probe-only Operations."""

    def invoke(
        _observation: RuntimeObservation,
        _handler: PackagedHandler,
        _payload: dict[str, Any],
        _timeout: float,
    ) -> KernelInvocationResult:
        raise AssertionError("test did not configure a Kernel invoker")

    return OperationServices(probe, invoke, _UnusedTargetFiles())


def spa(
    *args: str,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    executable: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the installed SPA command from the active project environment."""
    selected = str(executable) if executable is not None else shutil.which("spa")
    assert selected, "run tests in an installed SPA environment"
    return subprocess.run(
        [selected, *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
        input=stdin,
    )


def fake_aseprite(tmp_path: Path, body: str) -> Path:
    """Create a controlled executable with a macOS-style resource layout."""
    binary = tmp_path / "Aseprite.app" / "Contents" / "MacOS" / "aseprite"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    resource = binary.parent.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")
    return binary


def fake_probe_response(tmp_path: Path, response: str) -> Path:
    """Create a controlled Aseprite transport that returns one probe response."""
    quoted_response = shlex.quote(response)
    return fake_aseprite(
        tmp_path,
        f"""
request=
response_file=
echo_file=
for argument in "$@"; do
  case "$argument" in
    request=*) request=${{argument#request=}};;
    response=*) response_file=${{argument#response=}};;
    echo=*) echo_file=${{argument#echo=}};;
  esac
done
cp "$request" "$echo_file"
printf '%s' {quoted_response} > "$response_file"
""",
    )


def inject_palette_change(
    target: Path, entries: list[tuple[int, int, int, int]]
) -> None:
    """Add a second-Frame Palette Chunk unavailable through the public Lua API."""
    payload = bytearray(target.read_bytes())
    frame_offset = 128 + struct.unpack_from("<I", payload, 128)[0]
    colors = b"".join(struct.pack("<HBBBB", 0, *color) for color in entries)
    chunk_data = struct.pack("<III8x", len(entries), 0, len(entries) - 1) + colors
    chunk = struct.pack("<IH", len(chunk_data) + 6, 0x2019) + chunk_data
    frame_size = struct.unpack_from("<I", payload, frame_offset)[0]
    insert_at = frame_offset + 16
    old_chunk_count = struct.unpack_from("<H", payload, frame_offset + 6)[0]
    new_chunk_count = struct.unpack_from("<I", payload, frame_offset + 12)[0]
    struct.pack_into("<I", payload, frame_offset, frame_size + len(chunk))
    if new_chunk_count:
        struct.pack_into("<I", payload, frame_offset + 12, new_chunk_count + 1)
    if old_chunk_count != 0xFFFF:
        struct.pack_into("<H", payload, frame_offset + 6, old_chunk_count + 1)
    payload[insert_at:insert_at] = chunk
    struct.pack_into("<I", payload, 0, len(payload))
    target.write_bytes(payload)
