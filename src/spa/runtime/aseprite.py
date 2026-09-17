"""Discovery, isolated process execution, and private probe transport."""

import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time
from importlib.resources import files

from spa.contracts import (
    Diagnostics,
    NotFoundDetails,
    ProcessDetails,
    ProtocolDetails,
    ResourceDetails,
    RuntimeFacts,
    RuntimeRequest,
)
from spa.failures import RuntimeFailure

PROTOCOL_VERSION = 1
OUTPUT_LIMIT_BYTES = 65536


def _discover(requested: str | None) -> tuple[Path, Path, Path, str]:
    source = requested or os.environ.get("ASEPRITE_EXECUTABLE")
    selection_source = "explicit" if requested else "environment" if source else "path"
    discovered = Path(source).expanduser() if source else Path(shutil.which("aseprite") or "")
    searched = [source] if source else ["ASEPRITE_EXECUTABLE", "PATH:aseprite"]
    if not discovered.is_file() or not os.access(discovered, os.X_OK):
        raise RuntimeFailure(
            "executable_not_found", "environment", "Aseprite executable was not found or is not executable",
            NotFoundDetails(requested_path=requested, searched=searched),
        )
    canonical = discovered.resolve(strict=True)
    resource_candidates = [
        canonical.parent.parent / "Resources" / "data" / "gui.xml",
        canonical.parent.parent / "data" / "gui.xml",
        canonical.parent / "data" / "gui.xml",
    ]
    resource = next((path for path in resource_candidates if path.is_file()), None)
    if resource is None:
        raise RuntimeFailure(
            "resource_incomplete", "environment", "Aseprite gui.xml resource was not found",
            ResourceDetails(canonical_path=str(canonical), searched=[str(path) for path in resource_candidates]),
        )
    return discovered, canonical, resource, selection_source


def _run(command: list[str], env: dict[str, str], timeout: float) -> tuple[int, Diagnostics]:
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except OSError as exc:
        raise RuntimeFailure(
            "process_start_failed", "execution", str(exc),
            ProcessDetails(executable=command[0]),
        ) from exc
    assert process.stdout is not None and process.stderr is not None
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    streams = selectors.DefaultSelector()
    streams.register(process.stdout, selectors.EVENT_READ, "stdout")
    streams.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = time.monotonic() + timeout
    timed_out = False
    over_limit = False
    try:
        while streams.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in streams.select(timeout=remaining):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    streams.unregister(key.fileobj)
                    continue
                target = captured[key.data]
                exceeds = len(target) + len(chunk) > OUTPUT_LIMIT_BYTES
                target.extend(chunk[: max(0, OUTPUT_LIMIT_BYTES - len(target))])
                if exceeds:
                    over_limit = True
                    break
            if over_limit:
                break
        if timed_out or over_limit:
            if process.poll() is None:
                process.kill()
        try:
            status = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            status = process.wait()
            timed_out = True
    finally:
        streams.close()
        process.stdout.close()
        process.stderr.close()
    diagnostics = Diagnostics(
        stdout=captured["stdout"].decode("utf-8", errors="replace"),
        stderr=captured["stderr"].decode("utf-8", errors="replace"),
        exit_status=status,
    )
    if timed_out:
        raise RuntimeFailure("process_timeout", "execution", "Aseprite process timed out", ProcessDetails(executable=command[0], exit_status=status), diagnostics)
    if over_limit:
        raise RuntimeFailure("output_limit_exceeded", "execution", "Aseprite process output exceeded the limit", ProcessDetails(executable=command[0], exit_status=status), diagnostics)
    return status, diagnostics


def probe(request: RuntimeRequest) -> RuntimeFacts:
    discovered, canonical, resource, selection_source = _discover(request.aseprite)
    script = files("spa.kernel").joinpath("probe.lua")
    sentinel = {"nullable": None, "nested": [{"value": None}, [1, None, {"flag": True}]]}
    with tempfile.TemporaryDirectory(prefix="spa-info-") as work:
        request_file = Path(work) / "request.json"
        response_file = Path(work) / "response.json"
        echo_file = Path(work) / "echo.json"
        request_file.write_text(json.dumps({"protocol_version": PROTOCOL_VERSION, "echo": sentinel}), encoding="utf-8")
        env = os.environ.copy()
        env["ASEPRITE_USER_FOLDER"] = str(Path(work) / "aseprite-user")
        command = [
            str(canonical), "--batch", "--script-param", f"request={request_file}",
            "--script-param", f"response={response_file}",
            "--script-param", f"echo={echo_file}", "--script", str(script),
        ]
        status, diagnostics = _run(command, env, request.timeout_seconds)
        if not response_file.is_file():
            raise RuntimeFailure(
                "kernel_response_missing", "protocol", "Aseprite did not write a Kernel response",
                ProtocolDetails(response_path=str(response_file)), diagnostics,
            )
        try:
            if response_file.stat().st_size > OUTPUT_LIMIT_BYTES:
                raise ValueError("Kernel response exceeded the output limit")
            response = json.loads(response_file.read_text(encoding="utf-8"))
            if not isinstance(response, dict) or response.get("protocol_version") != PROTOCOL_VERSION:
                raise ValueError("unexpected Kernel Protocol version")
            if response.get("status") != "ok":
                raise ValueError(str(response.get("message", "Kernel probe failed")))
            if not echo_file.is_file():
                raise ValueError("Kernel JSON echo was not written")
            if echo_file.stat().st_size > OUTPUT_LIMIT_BYTES:
                raise ValueError("Kernel JSON echo exceeded the output limit")
            echo = json.loads(echo_file.read_text(encoding="utf-8"))
            if echo != {"protocol_version": PROTOCOL_VERSION, "echo": sentinel}:
                raise ValueError(f"Kernel JSON null/nested value round-trip changed: {echo!r}")
            if status != 0:
                raise ValueError(f"Aseprite exited with status {status} despite a success response")
            version = response["aseprite_version"]
            api_version = response["api_version"]
            if not isinstance(version, str) or not isinstance(api_version, int):
                raise ValueError("Kernel probe returned invalid version facts")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeFailure(
                "kernel_response_invalid", "protocol", f"Invalid Kernel response: {exc}",
                ProtocolDetails(response_path=str(response_file)), diagnostics,
            ) from exc
    return RuntimeFacts(
        selection_source=selection_source, requested_path=request.aseprite,
        discovered_path=str(discovered), canonical_path=str(canonical),
        resource_complete=True, resource_path=str(resource), aseprite_version=version, api_version=api_version,
    )
