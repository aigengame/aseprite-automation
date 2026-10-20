"""Helpers shared across test ownership areas."""

import dataclasses
import hashlib
import json
import os
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import textwrap
from collections.abc import Iterable, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any, get_args

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


def installed_cli() -> str:
    """Return the SPA command that the example recipes run.

    `SPA_TEST_INSTALLED_CLI` selects a wheel-installed CLI. Otherwise this is the
    `spa` command of the active project environment.
    """
    selected = os.environ.get("SPA_TEST_INSTALLED_CLI") or shutil.which("spa")
    assert selected, "run tests in an installed SPA environment"
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
        # Do not indent the shell branch: a quoted multi-line response would
        # receive the indentation inside its quotes.
        shell = (
            'if test -n "$echo"; then\n'
            + shell
            + "else\n"
            + f"printf '%s' {shlex.quote(kernel_response)} > \"$response\"\n"
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


def probe_answer(
    capabilities: Iterable[RuntimeCapability] = get_args(RuntimeCapability),
    *,
    aseprite_version: str = "test",
) -> str:
    """Return the probe response of a runtime that verifies capabilities."""
    return json.dumps(
        {
            "kernel_protocol_version": 1,
            "status": "ok",
            "aseprite_version": aseprite_version,
            "api_version": 41,
            "lua_version": "Lua 5.4",
            "verified_prerequisites": [
                "aseprite_scripting",
                "lua_file_io",
                "aseprite_json",
            ],
            "verified_capabilities": list(capabilities),
        }
    )


PROBE_ONLY_REFUSAL = "probe-only Aseprite: call refused"
"""The stderr line of a probe-only Aseprite for each call that is not a probe."""


def probe_only_aseprite(
    tmp_path: Path,
    capabilities: Iterable[RuntimeCapability] = get_args(RuntimeCapability),
) -> Path:
    """Answer the runtime probe, and refuse each other call.

    The probe answer verifies capabilities. A call without an echo= argument, for
    example a Kernel call, writes PROBE_ONLY_REFUSAL to stderr and exits 97. Thus a
    test of a refusal before the Kernel fails if the request gets to the Kernel.
    """
    answer = probe_answer(capabilities)
    shell = (
        'if test -z "$echo"; then\n'
        f"printf '%s\\n' {shlex.quote(PROBE_ONLY_REFUSAL)} >&2\n"
        "exit 97\n"
        "fi\n"
        'cp "$request" "$echo"\n'
        f"printf '%s' {shlex.quote(answer)} > \"$response\"\n"
    )
    python = (
        "if 'echo' not in arguments:\n"
        f"    print({PROBE_ONLY_REFUSAL!r}, file=sys.stderr)\n"
        "    sys.exit(97)\n"
        "Path(arguments['echo']).write_bytes(Path(arguments['request']).read_bytes())\n"
        f"Path(arguments['response']).write_text({answer!r}, encoding='utf-8')\n"
    )
    return controlled_aseprite(
        tmp_path, shell=CONTROLLED_SHELL_PRELUDE + shell, python=python
    )


def script_runtime(tmp_path: Path, body: str) -> Path:
    """Answer the runtime probe, then run body as the caller's script process."""
    probe = probe_answer(["aseprite_runtime_introspection"])
    driver = tmp_path / "runtime.py"
    driver.write_text(CONTROLLED_PYTHON_PRELUDE + body + "\n", encoding="utf-8")
    # On POSIX, keep the protocol stub independent of Python startup. The caller
    # process can still time out before it produces any output.
    return controlled_aseprite(
        tmp_path,
        shell=CONTROLLED_SHELL_PRELUDE
        + f"""is_probe=false
for argument in "$@"; do
  case "$argument" in */probe.lua) is_probe=true;; esac
done
if [ "$is_probe" = true ]; then
  cp "$request" "$echo"
  printf '%s' {shlex.quote(probe)} > "$response"
else
  exec {shlex.quote(sys.executable)} {shlex.quote(str(driver))} "$@"
fi
""",
        python="if any(Path(arg).name == 'probe.lua' for arg in sys.argv[1:]):\n"
        "    Path(arguments['echo']).write_bytes(Path(arguments['request']).read_bytes())\n"
        f"    Path(arguments['response']).write_text({probe!r}, encoding='utf-8')\n"
        "else:\n" + "\n".join("    " + line for line in body.splitlines()),
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


def write_group_opacity_and_blend(
    sprite: Path, opacity: Sequence[int], blend_mode: Sequence[int | None] = ()
) -> None:
    """Write the Group opacity and blend mode that batch SaveAs omits (#117).

    Aseprite 1.3.18.5 batch SaveAs does not save these Group fields. This sets the
    header flag that makes them valid. The n-th Group Layer chunk, in file order,
    gets opacity[n], and blend_mode[n] when that value is not None. The sprite
    must have exactly len(opacity) Groups.
    """
    assert not blend_mode or len(blend_mode) == len(opacity)
    payload = bytearray(sprite.read_bytes())
    flags = struct.unpack_from("<I", payload, 14)[0]
    struct.pack_into("<I", payload, 14, flags | 2)
    frame_offset = 128
    frame_size, frame_magic, chunk_count = struct.unpack_from(
        "<IHH", payload, frame_offset
    )
    assert frame_magic == 0xF1FA and frame_size > 16
    chunk_offset = frame_offset + 16
    groups = 0
    for _ in range(chunk_count):
        chunk_size, chunk_type = struct.unpack_from("<IH", payload, chunk_offset)
        assert chunk_size >= 6
        if (
            chunk_type == 0x2004
            and struct.unpack_from("<H", payload, chunk_offset + 8)[0] == 1
        ):
            assert groups < len(opacity), "the sprite has more Groups than values"
            payload[chunk_offset + 18] = opacity[groups]
            if blend_mode and blend_mode[groups] is not None:
                struct.pack_into("<H", payload, chunk_offset + 16, blend_mode[groups])
            groups += 1
        chunk_offset += chunk_size
    assert groups == len(opacity), f"the sprite has {groups} Groups"
    sprite.write_bytes(payload)


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


def controlled_runtime(binary: Path) -> RuntimeObservation:
    """Observe a controlled Aseprite from `controlled_aseprite` without a probe."""
    return dataclasses.replace(
        runtime_observation(),
        canonical_path=str(binary),
        resource_path=str(binary.parents[1] / "Resources" / "data" / "gui.xml"),
    )


# Lua fixture builders and request builders that the export, image, animation,
# tile, paint, plan, motion and MCP areas share. Each builder takes the session
# `runtime` and imports `run_lua` when it runs, because tests.native_invocation
# imports this module.

_EXPORT_FIXTURES = Path(__file__).parent / "export" / "fixtures"
_IMAGE_FIXTURES = Path(__file__).parent / "image" / "fixtures"
_TILE_FIXTURES = Path(__file__).parent / "tile" / "fixtures"


def export_image_choices(
    source: Path,
    destination: Path,
    *,
    frame_number: int = 1,
    if_exists: str = "fail",
    **choices: object,
) -> dict:
    """Return an Export Image request without an Aseprite path.

    The request exports the visible canvas of frame_number and preserves the
    color mode, color profile and transparency. Each choice replaces one field.
    """
    return {
        "source_sprite_file": str(source),
        "destination": {"path": str(destination), "if_exists": if_exists},
        "frame_number": frame_number,
        "export_image_area": {"kind": "canvas"},
        "layer_composition": {"mode": "visible"},
        "composition_color_mode": "preserve",
        "color_mode": "preserve",
        "color_profile": "preserve",
        "transparency": "preserve",
        **choices,
    }


def source_sprite(
    runtime: RuntimeObservation,
    tmp_path: Path,
    fixture_name: str = "rgb_frames.lua",
    **params: object,
) -> Path:
    """Write `source.aseprite` in tmp_path with an export Lua fixture.

    This adds the `out` parameter, checks the exit status and the written file,
    and returns the file.
    """
    from tests.native_invocation import run_lua

    source = tmp_path / "source.aseprite"
    lua = run_lua(_EXPORT_FIXTURES / fixture_name, runtime, out=source, **params)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    return source


def image_fixture(
    runtime: RuntimeObservation, tmp_path: Path, mode: str = "rgb"
) -> Path:
    """Write `source.aseprite` in tmp_path with `resize_targets.lua` for mode.

    This checks the exit status and the written file, and returns the file.
    """
    from tests.native_invocation import run_lua

    source = tmp_path / "source.aseprite"
    lua = run_lua(
        _IMAGE_FIXTURES / "resize_targets.lua", runtime, out=source, mode=mode
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    return source


def orientation_fixture(
    runtime: RuntimeObservation,
    tmp_path: Path,
    mode: str = "rgb",
    kind: str = "regular",
) -> Path:
    """Write `source.aseprite` in tmp_path with `orientation_targets.lua`.

    This checks the exit status and the written file, and returns the file.
    """
    from tests.native_invocation import run_lua

    source = tmp_path / "source.aseprite"
    lua = run_lua(
        _IMAGE_FIXTURES / "orientation_targets.lua",
        runtime,
        out=source,
        mode=mode,
        kind=kind,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    return source


def inspect_orientation(
    runtime: RuntimeObservation, source: Path, tmp_path: Path, layer: int = 1
) -> dict:
    """Return the Cels of layer in source that `inspect_orientation.lua` reads.

    The fixture writes `native.json` in tmp_path.
    """
    from tests.native_invocation import run_lua

    output = tmp_path / "native.json"
    lua = run_lua(
        _IMAGE_FIXTURES / "inspect_orientation.lua",
        runtime,
        source=source,
        out=output,
        layer=layer,
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(output.read_text())


def aseprite_chunks(raw: bytes | bytearray):
    """Yield the offset, type and data of each chunk of an `.aseprite` file."""
    frame_at = 128
    while frame_at < len(raw):
        size = struct.unpack_from("<I", raw, frame_at)[0]
        at = frame_at + 16
        while at < frame_at + size:
            length, kind = struct.unpack_from("<IH", raw, at)
            yield at, kind, bytes(raw[at + 6 : at + length])
            at += length
        frame_at += size


_MULTIPLY = 1  # native blend mode MULTIPLY in the file format
# Opacity and blend mode of each Group, in file order, for each patched fixture.
_SNAPSHOT_GROUP_FIELDS = {
    "composition": ((128, 255), ()),
    "blend": ((255,), (_MULTIPLY,)),
    "indexed-blend": ((255,), (_MULTIPLY,)),
    "indexed-opacity": ((128,), ()),
    "hidden-group": ((128, 192), (_MULTIPLY, None)),
}


def snapshot_fixture(
    runtime: RuntimeObservation,
    tmp_path: Path,
    mode: str = "rgb",
    *,
    script: str = "snapshot_targets.lua",
) -> Path:
    """Write `<mode>.aseprite` in tmp_path with an image Lua fixture.

    The fixture is `snapshot_targets.lua` unless script names another one. This
    checks the exit status. Then it writes the file fields that batch SaveAs
    omits: the Group opacity and blend mode of the patched modes, and the
    precise reference bounds of the `reference` mode.
    """
    from tests.native_invocation import run_lua

    source = tmp_path / f"{mode}.aseprite"
    lua = run_lua(_IMAGE_FIXTURES / script, runtime, out=source, mode=mode)
    assert lua.returncode == 0, process_diagnostics(lua)
    if mode in _SNAPSHOT_GROUP_FIELDS:
        write_group_opacity_and_blend(source, *_SNAPSHOT_GROUP_FIELDS[mode])
    elif mode == "reference":
        raw = bytearray(source.read_bytes())
        for at, kind, _ in aseprite_chunks(raw):
            if kind == 0x2006:
                struct.pack_into("<4i", raw, at + 10, 32768, -81920, 950272, 475136)
        source.write_bytes(raw)
    return source


def tileset_lifecycle_sprite(
    runtime: RuntimeObservation, source: Path, **params: object
) -> None:
    """Write the Tileset rebind Sprite of `tile/fixtures/tileset_lifecycle.lua`."""
    from tests.native_invocation import run_lua

    lua = run_lua(
        _TILE_FIXTURES / "tileset_lifecycle.lua", runtime, source=source, **params
    )
    assert lua.returncode == 0, process_diagnostics(lua)


def color_mode_conversion(source: str, target: str) -> dict:
    """Return the `conversion` object that changes source to target Color Mode.

    A change to grayscale uses `luma`. A change to indexed uses the default RGB
    map algorithm and best-fit criteria; from RGB it also uses no dithering.
    The same mode gives only the target `color_mode`.
    """
    options: dict = {"color_mode": target}
    if source != target:
        if target == "grayscale":
            options["to_gray"] = "luma"
        if target == "indexed":
            options.update(
                rgb_map_algorithm="default", color_best_fit_criteria="default"
            )
            if source == "rgb":
                options["dithering"] = {"algorithm": "none"}
    return {"source_color_mode": source, "target": options}


def change_sprite_color_mode(
    source: Path, target: Path, conversion: dict
) -> tuple[int, dict]:
    """Run `spa sprite change-color-mode` and return `(returncode, envelope)`.

    This adds the Source and Target fields with `in_place` and `overwrite`
    False. The envelope gets the schema check of `run`.
    """
    from tests.native_invocation import run

    outcome = run(
        "sprite change-color-mode",
        {
            "source_sprite_file": str(source),
            "target_sprite_file": str(target),
            "in_place": False,
            "overwrite": False,
            "conversion": conversion,
        },
    )
    return outcome.returncode, outcome.envelope


# Shared e2e builders for the Plan, Layer, Cel, Sprite, Tag and Motion tests.
# tests.native_invocation imports this module, so these functions import it in
# their bodies.
_MOTION_FIXTURES = Path(__file__).parent / "motion" / "fixtures"
_CEL_FIXTURES = Path(__file__).parent / "cel" / "fixtures"
_FRAME_FIXTURES = Path(__file__).parent / "frame" / "fixtures"
_OBSERVER = Path(__file__).parent / "fixtures" / "observe_cli.py"


def motion_sprite(
    runtime: RuntimeObservation, tmp_path: Path, **parameters: object
) -> Path:
    """Write the posed motion Sprite of `poses.lua` to tmp_path, and return its path."""
    from tests.native_invocation import run_lua

    source = tmp_path / "source.aseprite"
    lua = run_lua(_MOTION_FIXTURES / "poses.lua", runtime, out=source, **parameters)
    assert lua.returncode == 0, process_diagnostics(lua)
    assert source.is_file()
    return source


def inspect_motion(runtime: RuntimeObservation, source: Path, tmp_path: Path) -> dict:
    """Read the native Frames and Cels of source with `inspect.lua`."""
    from tests.native_invocation import run_lua

    out = tmp_path / "inspection.json"
    lua = run_lua(_MOTION_FIXTURES / "inspect.lua", runtime, source=source, out=out)
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(out.read_text())


def motion_curves() -> dict:
    """Return motion inputs that move Layer 1 over Frames 1 to 5 and fade it in."""
    return {
        "layer": {"layer_path": [1]},
        "from_frame": 1,
        "to_frame": 5,
        "position_offsets": {
            "interpolation": "linear",
            "rounding": "nearest-away-from-zero",
            "keys": [
                {"frame_number": 1, "offset": {"x": 0, "y": 0}},
                {"frame_number": 5, "offset": {"x": 2, "y": -2}},
            ],
        },
        "opacity": {
            "interpolation": "linear",
            "rounding": "floor",
            "keys": [
                {"frame_number": 1, "opacity": 0},
                {"frame_number": 5, "opacity": 255},
            ],
        },
    }


def motion_request(source: Path, target: Path, inputs: dict) -> dict[str, Any]:
    """Return a `motion apply` request from source to target with inputs.

    `in_place` is true when target is source, and `overwrite` is true when target
    already exists.
    """
    return {
        "source_sprite_file": str(source),
        "target_sprite_file": str(target),
        "in_place": source == target,
        "overwrite": target.exists(),
        **inputs,
    }


def cel_relationships_sprite(runtime: RuntimeObservation, target: Path) -> None:
    """Write the linked and unlinked Cel Sprite of `relationships.lua` to target."""
    from tests.native_invocation import run_lua

    lua = run_lua(_CEL_FIXTURES / "relationships.lua", runtime, out=target)
    assert lua.returncode == 0, process_diagnostics(lua)


def native_link_status(
    runtime: RuntimeObservation, sprite_file: Path, out: Path
) -> bool:
    """Return whether Cels 1 and 2 of Layer 1 in sprite_file share one image.

    `inspect_links.lua` reads the native Sprite and writes its report to out.
    """
    from tests.native_invocation import run_lua

    lua = run_lua(
        _FRAME_FIXTURES / "inspect_links.lua", runtime, source=sprite_file, out=out
    )
    assert lua.returncode == 0, process_diagnostics(lua)
    return json.loads(out.read_text(encoding="utf-8"))["linked"]


def observe_cli(
    case: str,
    command: str,
    request: dict[str, Any],
    observations: Path,
    *,
    seam: str,
    aseprite: str | Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], dict[str, Any]]:
    """Run `spa <command>` in the observer script, and return its process and records.

    `tests/fixtures/observe_cli.py` replaces the SPA adapters of seam in the CLI
    process before the entry point runs, injects the fault of case, and writes
    what it observed to observations. The seams are:

    - "invoke": record the completion events of a standalone mutation, and count
      its native invocations and Target Commits.
    - "invoke_direct": count Plan native invocations and Target Commits, and
      change the native Plan response.
    - "run": count probe and handler processes and Target Commits, and run each
      handler in the native I/O wrapper `tests/fixtures/observe_cli.lua`.
    - "staged_path": block each staged path so the native save fails, count
      Target Commits, and record that the discard returned with no staged file.

    This runner adds aseprite, or the `SPA_TEST_ASEPRITE` value, to request, and
    validates the envelope against the schema of command. Return the process, its
    envelope, and the observations.
    """
    from jsonschema import ValidationError

    from tests.native_invocation import validate_envelope

    assert seam in ("invoke", "invoke_direct", "run", "staged_path"), (
        f"unknown observer seam {seam!r}"
    )
    assert "aseprite" not in request, "give the Aseprite path as aseprite="
    cli = shutil.which("spa")
    assert cli, "run tests in an installed SPA environment"
    selected = os.environ["SPA_TEST_ASEPRITE"] if aseprite is None else aseprite
    payload = json.dumps({**request, "aseprite": str(selected)})
    process = subprocess.run(
        [
            sys.executable,
            str(_OBSERVER),
            seam,
            case,
            str(observations),
            cli,
            *command.split(),
            "--input-json",
            payload,
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        envelope = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(process_diagnostics(process)) from error
    try:
        validate_envelope(command, envelope)
    except ValidationError as error:
        error.add_note(process_diagnostics(process))
        raise
    return process, envelope, json.loads(observations.read_text())
