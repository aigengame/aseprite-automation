"""Helpers shared across test ownership areas."""

import hashlib
import os
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import textwrap
from importlib.resources import files
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
from tests.native_entry import python_entry


def icc_fixture_path(identity: str) -> Path:
    """Resolve a packaged ICC or an explicitly supplied Apple input."""
    if identity != "display_p3":
        return Path(str(files("spa.kernel").joinpath(f"color/profiles/{identity}.icc")))
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
        encoding="utf-8",
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


def cli_entry_command(
    kind: str, work_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    """Select the real CLI entries shared by UTF-8 and MCP-child regressions."""
    if kind == "main":
        return [
            sys.executable,
            "-X",
            "utf8=0",
            "-c",
            "from spa.bootstrap import main; main()",
        ]
    if kind == "wheel":
        return [isolated_wheel_cli(work_directory, monkeypatch)]
    executable = shutil.which("spa")
    assert executable, "run tests in an installed SPA environment"
    return [executable]


CONTROLLED_PYTHON_PRELUDE = (
    "import os, sys, time\n"
    "from pathlib import Path\n"
    "sys.stdout.reconfigure(encoding='utf-8', newline='\\n')\n"
    "sys.stderr.reconfigure(encoding='utf-8', newline='\\n')\n"
    "arguments = dict(arg.split('=', 1) for arg in sys.argv[1:] if '=' in arg)\n"
)
"""Common imports, UTF-8 streams, and the key=value arguments of a Python body."""

CONTROLLED_SHELL_PRELUDE = """request=
response=
echo=
for argument in "$@"; do
  case "$argument" in
    request=*) request=${argument#request=};;
    response=*) response=${argument#response=};;
    echo=*) echo=${argument#echo=};;
  esac
done
"""
"""Set the request, response, and echo paths of a shell body from its arguments."""


def _add_aseprite_resources(executable_directory: Path) -> None:
    resource = executable_directory.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")


def fake_aseprite(tmp_path: Path, body: str) -> Path:
    """Create a controlled shell executable with a macOS-style resource layout."""
    binary = tmp_path / "Aseprite.app" / "Contents" / "MacOS" / "aseprite"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    _add_aseprite_resources(binary.parent)
    return binary


def python_aseprite(tmp_path: Path, body: str) -> Path:
    """Create a controlled Python entry with the same layout on every platform."""
    directory = tmp_path / "Aseprite.app" / "Contents" / "MacOS"
    binary = python_entry(
        directory, "aseprite", CONTROLLED_PYTHON_PRELUDE + body + "\n"
    )
    _add_aseprite_resources(directory)
    return binary


def controlled_aseprite(tmp_path: Path, *, shell: str, python: str) -> Path:
    """Create one controlled Aseprite behaviour from the body for this platform.

    POSIX runs the shell body, which keeps its process structure, such as exec and
    pipes. Windows runs the Python body in a native entry.
    """
    if os.name == "nt":
        return python_aseprite(tmp_path, python)
    return fake_aseprite(tmp_path, shell)


def exiting_aseprite(
    tmp_path: Path, *, stdout: str = "", stderr: str = "", status: int = 0
) -> Path:
    """Write one optional line to each output stream, then exit with status.

    A negative status ends the process with that signal. Only POSIX has this case.
    """
    shell: list[str] = []
    python: list[str] = []
    if stdout:
        shell.append(f"printf '%s\\n' {shlex.quote(stdout)}")
        python.append(f"print({stdout!r})")
    if stderr:
        shell.append(f"printf '%s\\n' {shlex.quote(stderr)} >&2")
        python.append(f"print({stderr!r}, file=sys.stderr)")
    if status < 0:
        assert os.name != "nt", "signal termination is a POSIX fixture"
        shell.append(f"kill -{signal.Signals(-status).name.removeprefix('SIG')} $$")
    else:
        shell.append(f"exit {status}")
        python.append(f"sys.exit({status})")
    return controlled_aseprite(
        tmp_path, shell="\n".join(shell) + "\n", python="\n".join(python)
    )


def responding_aseprite(
    tmp_path: Path, response: str, *, echo: str | None = None, status: int = 0
) -> Path:
    """Write response to the response= file, then exit with status.

    When echo is given, first write it to the echo= file.
    """
    shell = CONTROLLED_SHELL_PRELUDE
    python = ""
    if echo is not None:
        shell += f"printf '%s' {shlex.quote(echo)} > \"$echo\"\n"
        python += f"Path(arguments['echo']).write_text({echo!r}, encoding='utf-8')\n"
    shell += f"printf '%s' {shlex.quote(response)} > \"$response\"\nexit {status}\n"
    python += (
        f"Path(arguments['response']).write_text({response!r}, encoding='utf-8')\n"
        f"sys.exit({status})"
    )
    return controlled_aseprite(tmp_path, shell=shell, python=python)


def recording_aseprite(tmp_path: Path, record: Path, response: str) -> Path:
    """Append one line of tab-separated arguments to record, then write response."""
    return controlled_aseprite(
        tmp_path,
        shell=(
            "line=\n"
            "separator=\n"
            'for argument in "$@"; do\n'
            '  line="$line$separator$argument"\n'
            "  separator='\t'\n"
            "done\n"
            f"printf '%s\\n' \"$line\" >> {shlex.quote(str(record))}\n"
            + CONTROLLED_SHELL_PRELUDE
            + f"printf '%s' {shlex.quote(response)} > \"$response\"\n"
        ),
        python=(
            f"with Path({str(record)!r}).open('a', encoding='utf-8') as stream:\n"
            "    stream.write('\\t'.join(sys.argv[1:]) + '\\n')\n"
            f"Path(arguments['response']).write_text({response!r}, encoding='utf-8')"
        ),
    )


def fake_probe_response(
    tmp_path: Path, response: str, *, kernel_response: str | None = None
) -> Path:
    """Create a controlled Aseprite transport that returns one probe response.

    A probe passes an echo= argument. With kernel_response, an invocation without
    that argument receives kernel_response instead of the probe response.
    """
    shell = (
        f'cp "$request" "$echo"\nprintf \'%s\' {shlex.quote(response)} > "$response"\n'
    )
    python = (
        "Path(arguments['echo']).write_bytes(Path(arguments['request']).read_bytes())\n"
        f"Path(arguments['response']).write_text({response!r}, encoding='utf-8')\n"
    )
    if kernel_response is not None:
        shell = (
            'if test -n "$echo"; then\n'
            + textwrap.indent(shell, "  ")
            + "else\n"
            + f"  printf '%s' {shlex.quote(kernel_response)} > \"$response\"\n"
            + "fi\n"
        )
        python = (
            "if 'echo' in arguments:\n"
            + textwrap.indent(python, "    ")
            + "else:\n"
            + f"    Path(arguments['response']).write_text({kernel_response!r}, "
            "encoding='utf-8')\n"
        )
    return controlled_aseprite(
        tmp_path, shell=CONTROLLED_SHELL_PRELUDE + shell, python=python
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
