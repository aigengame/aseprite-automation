"""Discovery, isolated process execution, and private probe transport."""

import json
import os
import selectors
import shutil
import subprocess
import tempfile
import time
from importlib.resources import files
from pathlib import Path

from spa.contracts import (
    Diagnostics,
    RuntimeRequest,
)
from spa.ports import (
    DiscoveryEvidence,
    HandlerEvidence,
    LaunchEvidence,
    ProcessEvidence,
    ResourceEvidence,
    ResponseEvidence,
    RuntimeIssue,
    RuntimeObservation,
)
from spa.runtime.invocation import prepare_invocation

KERNEL_PROTOCOL_VERSION = 1
OUTPUT_LIMIT_BYTES = 65536


def _discover(requested: str | None) -> tuple[Path, Path, Path, str]:
    source = requested or os.environ.get("SPA_ASEPRITE_EXECUTABLE")
    selection_source = "explicit" if requested else "environment" if source else "path"
    searched = [source] if source else ["SPA_ASEPRITE_EXECUTABLE", "PATH:aseprite"]
    try:
        discovered = (
            Path(source).expanduser()
            if source
            else Path(shutil.which("aseprite") or "")
        )
        if not discovered.is_file() or not os.access(discovered, os.X_OK):
            raise RuntimeIssue(
                "discovery_absent",
                "Aseprite executable was not found or is not executable",
                DiscoveryEvidence(requested_path=requested, searched=searched),
            )
        canonical = discovered.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise RuntimeIssue(
            "discovery_absent",
            "Aseprite executable was not found or is not executable",
            DiscoveryEvidence(requested_path=requested, searched=searched),
        ) from exc
    resource_candidates = [
        canonical.parent.parent / "Resources" / "data" / "gui.xml",
        canonical.parent.parent / "data" / "gui.xml",
        canonical.parent / "data" / "gui.xml",
    ]
    resource = next((path for path in resource_candidates if path.is_file()), None)
    if resource is None:
        raise RuntimeIssue(
            "resources_absent",
            "Aseprite gui.xml resource was not found",
            ResourceEvidence(
                canonical_path=str(canonical),
                searched=[str(path) for path in resource_candidates],
            ),
        )
    return discovered, canonical, resource, selection_source


def _run(
    command: list[str],
    env: dict[str, str],
    timeout: float,
    canonical_executable: Path,
) -> tuple[int, Diagnostics]:
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
    except OSError as exc:
        raise RuntimeIssue(
            "launch_failed",
            str(exc),
            LaunchEvidence(executable=str(canonical_executable)),
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
        if (timed_out or over_limit) and process.poll() is None:
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
        raise RuntimeIssue(
            "deadline",
            "Aseprite process timed out",
            ProcessEvidence(executable=str(canonical_executable), exit_status=status),
            diagnostics,
        )
    if over_limit:
        raise RuntimeIssue(
            "output_overflow",
            "Aseprite process output exceeded the limit",
            ProcessEvidence(executable=str(canonical_executable), exit_status=status),
            diagnostics,
        )
    return status, diagnostics


def _process_failure(
    status: int, executable: Path, diagnostics: Diagnostics
) -> RuntimeIssue:
    reason = (
        f"terminated by signal {-status}"
        if status < 0
        else f"exited with status {status}"
    )
    return RuntimeIssue(
        "process_failed",
        f"Aseprite {reason} before writing a complete Kernel response",
        ProcessEvidence(executable=str(executable), exit_status=status),
        diagnostics,
    )


def probe(request: RuntimeRequest) -> RuntimeObservation:
    discovered, canonical, resource, selection_source = _discover(request.aseprite)
    script = files("spa.kernel").joinpath("probe.lua")
    sentinel = {
        "nullable": None,
        "nested": [{"value": None}, [1, None, {"flag": True}]],
    }
    try:
        workspace = tempfile.TemporaryDirectory(prefix="spa-info-")
    except OSError as exc:
        raise RuntimeIssue(
            "launch_failed",
            f"Could not create Aseprite invocation workspace: {exc}",
            LaunchEvidence(executable=str(canonical)),
        ) from exc
    with workspace as work:
        request_file = Path(work) / "request.json"
        response_file = Path(work) / "response.json"
        echo_file = Path(work) / "echo.json"
        try:
            request_file.write_text(
                json.dumps(
                    {
                        "kernel_protocol_version": KERNEL_PROTOCOL_VERSION,
                        "echo": sentinel,
                    }
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            raise RuntimeIssue(
                "launch_failed",
                f"Could not write Aseprite Kernel request: {exc}",
                LaunchEvidence(executable=str(canonical)),
            ) from exc
        prepared = prepare_invocation(canonical, resource, Path(work))
        command = [
            str(prepared.executable),
            "--batch",
            "--script-param",
            f"request={request_file}",
            "--script-param",
            f"response={response_file}",
            "--script-param",
            f"echo={echo_file}",
            "--script",
            str(script),
        ]
        status, diagnostics = _run(
            command, prepared.environment, request.timeout_seconds, canonical
        )
        if not response_file.is_file():
            if status != 0:
                raise _process_failure(status, canonical, diagnostics)
            raise RuntimeIssue(
                "response_absent",
                "Aseprite did not write a Kernel response",
                ResponseEvidence(response_path=str(response_file)),
                diagnostics,
            )
        try:
            if response_file.stat().st_size > OUTPUT_LIMIT_BYTES:
                raise ValueError("Kernel response exceeded the output limit")
            response = json.loads(response_file.read_text(encoding="utf-8"))
            if (
                not isinstance(response, dict)
                or type(response.get("kernel_protocol_version")) is not int
                or response["kernel_protocol_version"] != KERNEL_PROTOCOL_VERSION
            ):
                raise ValueError("unexpected Kernel Protocol version")
            response_status = response.get("status")
            if response_status == "error":
                reason = response.get("message")
                if not isinstance(reason, str):
                    raise ValueError("Kernel error response has no string message")
                raise RuntimeIssue(
                    "handler_rejected",
                    f"Kernel probe failed: {reason}",
                    HandlerEvidence(response_path=str(response_file), reason=reason),
                    diagnostics,
                )
            if response_status != "ok":
                raise ValueError("unknown Kernel response status")
            if not echo_file.is_file():
                raise ValueError("Kernel JSON echo was not written")
            if echo_file.stat().st_size > OUTPUT_LIMIT_BYTES:
                raise ValueError("Kernel JSON echo exceeded the output limit")
            echo = json.loads(echo_file.read_text(encoding="utf-8"))
            expected_echo = {
                "kernel_protocol_version": KERNEL_PROTOCOL_VERSION,
                "echo": sentinel,
            }
            if json.dumps(echo, sort_keys=True, allow_nan=False) != json.dumps(
                expected_echo, sort_keys=True, allow_nan=False
            ):
                raise ValueError(
                    f"Kernel JSON null/nested value round-trip changed: {echo!r}"
                )
            if status != 0:
                raise RuntimeIssue(
                    "exit_mismatch",
                    f"Aseprite exited with status {status} despite a success response",
                    ProcessEvidence(executable=str(canonical), exit_status=status),
                    diagnostics,
                )
            version = response["aseprite_version"]
            api_version = response["api_version"]
            if not isinstance(version, str) or type(api_version) is not int:
                raise TypeError("Kernel probe returned invalid version facts")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            if status != 0:
                raise _process_failure(status, canonical, diagnostics) from exc
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Kernel response: {exc}",
                ResponseEvidence(response_path=str(response_file)),
                diagnostics,
            ) from exc
    return RuntimeObservation(
        selection_source=selection_source,
        requested_path=request.aseprite,
        discovered_path=str(discovered),
        canonical_path=str(canonical),
        resource_path=str(resource),
        aseprite_version=version,
        api_version=api_version,
    )
