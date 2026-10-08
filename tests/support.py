"""Helpers shared across test ownership areas."""

import hashlib
import os
import shlex
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spa.contracts.ports import (
    KernelInvocationResult,
    OperationServices,
    PackagedHandler,
    RuntimeObservation,
    RuntimeProbe,
    TargetCommitObservation,
)
from spa.contracts.public import RuntimeCapability


def caller_apple_p3() -> Path:
    """Use only an explicitly supplied input; never locate or download Apple bytes."""
    configured = os.environ.get("SPA_TEST_APPLE_P3_ICC")
    if not configured:
        pytest.skip("set SPA_TEST_APPLE_P3_ICC to test caller-supplied Apple P3")
    path = Path(configured).expanduser()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0"
    ), "the supplied Apple profile is not the previously admitted input"
    return path


def process_diagnostics(run: subprocess.CompletedProcess[str]) -> str:
    """Describe a failed captured process, including POSIX signal names."""
    failure = subprocess.CalledProcessError(run.returncode, run.args)
    return (
        f"{failure}\nexit status: {run.returncode}\n"
        f"stdout:\n{run.stdout}\nstderr:\n{run.stderr}"
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


def isolated_wheel_cli(work_directory: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Select the wheel CLI and isolate consumer calls from checkout imports."""
    selected = os.environ.get("SPA_TEST_INSTALLED_CLI")
    if not selected:
        pytest.skip("SPA_TEST_INSTALLED_CLI does not select a wheel-installed CLI")
    monkeypatch.chdir(work_directory)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    return selected


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
    target: Path,
    entries: list[tuple[int, int, int, int]],
    *,
    frame_number: int = 2,
) -> None:
    """Add a Palette Chunk unavailable through the public Lua API."""
    payload = bytearray(target.read_bytes())
    frame_offset = 128
    for _ in range(1, frame_number):
        frame_offset += struct.unpack_from("<I", payload, frame_offset)[0]
    colors = b"".join(struct.pack("<HBBBB", 0, *color) for color in entries)
    chunk_data = struct.pack("<III8x", len(entries), 0, len(entries) - 1) + colors
    chunk = struct.pack("<IH", len(chunk_data) + 6, 0x2019) + chunk_data
    frame_size = struct.unpack_from("<I", payload, frame_offset)[0]
    insert_at = frame_offset + 16
    old_chunk_count = struct.unpack_from("<H", payload, frame_offset + 6)[0]
    new_chunk_count = struct.unpack_from("<I", payload, frame_offset + 12)[0]
    struct.pack_into("<I", payload, frame_offset, frame_size + len(chunk))
    chunk_count = new_chunk_count if old_chunk_count == 0xFFFF else old_chunk_count
    struct.pack_into("<H", payload, frame_offset + 6, min(chunk_count + 1, 0xFFFF))
    struct.pack_into("<I", payload, frame_offset + 12, chunk_count + 1)
    payload[insert_at:insert_at] = chunk
    struct.pack_into("<I", payload, 0, len(payload))
    target.write_bytes(payload)


def clear_first_saved_layer_uuid(source: Path, layer_name: str) -> None:
    """Make the first named Layer in a native fixture lack a saved UUID."""
    payload = bytearray(source.read_bytes())
    frame_offset = 128
    frame_size, frame_magic, chunk_count = struct.unpack_from(
        "<IHH", payload, frame_offset
    )
    assert frame_magic == 0xF1FA and frame_size > 16
    chunk_offset = frame_offset + 16
    for _ in range(chunk_count):
        chunk_size, chunk_type = struct.unpack_from("<IH", payload, chunk_offset)
        assert chunk_size >= 6
        if chunk_type == 0x2004:
            assert chunk_size >= 24
            name_length = struct.unpack_from("<H", payload, chunk_offset + 22)[0]
            name = payload[chunk_offset + 24 : chunk_offset + 24 + name_length]
            if name == layer_name.encode("utf-8"):
                uuid_offset = chunk_offset + 24 + name_length
                layer_type = struct.unpack_from("<H", payload, chunk_offset + 8)[0]
                if layer_type == 2:
                    uuid_offset += 4  # Tilemap's Tileset index precedes its UUID.
                assert uuid_offset + 16 <= chunk_offset + chunk_size
                assert any(payload[uuid_offset : uuid_offset + 16])
                payload[uuid_offset : uuid_offset + 16] = bytes(16)
                source.write_bytes(payload)
                return
        chunk_offset += chunk_size
    raise AssertionError(f"fixture has no Layer chunk named {layer_name!r}")


def runtime_observation(*capabilities: RuntimeCapability) -> RuntimeObservation:
    return RuntimeObservation(
        selection_source="explicit",
        requested_path="/aseprite",
        discovered_path="/aseprite",
        canonical_path="/aseprite",
        resource_path="/data/gui.xml",
        aseprite_version="test",
        api_version=41,
        lua_version="Lua 5.4",
        verified_prerequisites=(
            "aseprite_scripting",
            "lua_file_io",
            "aseprite_json",
        ),
        verified_capabilities=capabilities,
    )
