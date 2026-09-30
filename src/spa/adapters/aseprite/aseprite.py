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
from typing import Any, Literal, cast, get_args

from spa.adapters.aseprite.invocation import prepare_invocation
from spa.contracts.ports import (
    DiscoveryEvidence,
    HandlerEvidence,
    KernelInvocationResult,
    LaunchEvidence,
    PackagedHandler,
    PackagedResource,
    ProcessEvidence,
    ResourceEvidence,
    ResponseEvidence,
    RuntimeCompatibilityEvidence,
    RuntimeIssue,
    RuntimeObservation,
)
from spa.contracts.public import (
    Diagnostics,
    ProbePrerequisite,
    RuntimeCapability,
    RuntimeCompatibilityDetails,
    RuntimeRequest,
)

KERNEL_PROTOCOL_VERSION = 1
OUTPUT_LIMIT_BYTES = 65536
CAPABILITY_PROBE_RESOURCE = PackagedResource("capability_probe", "capability_probe.lua")
PROBE_PREREQUISITES: frozenset[ProbePrerequisite] = frozenset(
    {"aseprite_scripting", "lua_file_io", "aseprite_json"}
)


def _discover(
    requested: str | None,
) -> tuple[Path, Path, Path, Literal["explicit", "environment", "path"]]:
    source = requested or os.environ.get("SPA_ASEPRITE_EXECUTABLE")
    selection_source: Literal["explicit", "environment", "path"] = (
        "explicit" if requested else "environment" if source else "path"
    )
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
                fileobj = key.fileobj
                file_descriptor = (
                    fileobj if isinstance(fileobj, int) else fileobj.fileno()
                )
                chunk = os.read(file_descriptor, 8192)
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


def _resource_arguments(resources: tuple[PackagedResource, ...]) -> list[str]:
    arguments: list[str] = []
    for resource in resources:
        path = files("spa.kernel").joinpath(resource.package_name)
        arguments.extend(("--script-param", f"{resource.parameter_name}={path}"))
    return arguments


def probe(
    request: RuntimeRequest, resources: tuple[PackagedResource, ...] = ()
) -> RuntimeObservation:
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
        capability_sprite = Path(work) / "capability.aseprite"
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
            "--script-param",
            f"capability_sprite={capability_sprite}",
            "--script-param",
            f"workspace={work}",
            *_resource_arguments((CAPABILITY_PROBE_RESOURCE,)),
            *_resource_arguments(resources),
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
            lua_version = response["lua_version"]
            verified_prerequisites = response["verified_prerequisites"]
            verified_capabilities = response["verified_capabilities"]
            if (
                not isinstance(version, str)
                or type(api_version) is not int
                or not isinstance(lua_version, str)
                or not isinstance(verified_prerequisites, list)
                or not all(
                    isinstance(prerequisite, str)
                    for prerequisite in verified_prerequisites
                )
                or not isinstance(verified_capabilities, list)
                or not all(
                    isinstance(capability, str) for capability in verified_capabilities
                )
            ):
                raise TypeError("Kernel probe returned invalid runtime facts")
            if set(verified_prerequisites) != PROBE_PREREQUISITES:
                raise ValueError(
                    "Kernel probe did not verify every required probe prerequisite"
                )
            supported_capabilities = set(get_args(RuntimeCapability))
            if any(
                capability not in supported_capabilities
                for capability in verified_capabilities
            ):
                raise ValueError("Kernel probe returned an unknown runtime capability")
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
        lua_version=lua_version,
        verified_prerequisites=cast(
            tuple[ProbePrerequisite, ...], tuple(verified_prerequisites)
        ),
        verified_capabilities=cast(
            tuple[RuntimeCapability, ...], tuple(verified_capabilities)
        ),
    )


def invoke(
    observation: RuntimeObservation,
    handler: PackagedHandler,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> KernelInvocationResult:
    """Invoke one fixed packaged handler and return its private result object."""
    return _invoke_at(
        Path(observation.canonical_path),
        Path(observation.resource_path),
        handler,
        payload,
        timeout_seconds,
    )


def invoke_direct(
    request: RuntimeRequest,
    handler: PackagedHandler,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> KernelInvocationResult:
    """Discover and execute a handler in one Aseprite process without a probe process."""
    _, canonical, resource, _ = _discover(request.aseprite)
    return _invoke_at(
        canonical,
        resource,
        handler,
        payload,
        timeout_seconds,
        with_capability_probe=True,
    )


def _invoke_at(
    canonical: Path,
    resource: Path,
    handler: PackagedHandler,
    payload: dict[str, Any],
    timeout_seconds: float,
    *,
    with_capability_probe: bool = False,
) -> KernelInvocationResult:
    handler_name = handler.resource_name
    script = files("spa.kernel").joinpath(f"{handler_name}.lua")
    try:
        workspace = tempfile.TemporaryDirectory(prefix=f"spa-{handler_name}-")
    except OSError as exc:
        raise RuntimeIssue(
            "launch_failed",
            f"Could not create Aseprite invocation workspace: {exc}",
            LaunchEvidence(executable=str(canonical)),
        ) from exc
    with workspace as work:
        request_file = Path(work) / "request.json"
        response_file = Path(work) / "response.json"
        try:
            request_file.write_text(
                json.dumps(
                    {
                        "kernel_protocol_version": KERNEL_PROTOCOL_VERSION,
                        "payload": payload,
                    },
                    allow_nan=False,
                ),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError) as exc:
            raise RuntimeIssue(
                "launch_failed",
                f"Could not write Aseprite Kernel request: {exc}",
                LaunchEvidence(executable=str(canonical)),
            ) from exc
        prepared = prepare_invocation(canonical, resource, Path(work))
        capability_arguments = (
            [
                "--script-param",
                f"capability_sprite={Path(work) / 'capability.aseprite'}",
                *_resource_arguments((CAPABILITY_PROBE_RESOURCE,)),
            ]
            if with_capability_probe
            else []
        )
        command = [
            str(prepared.executable),
            "--batch",
            "--script-param",
            f"request={request_file}",
            "--script-param",
            f"response={response_file}",
            "--script-param",
            f"workspace={work}",
            *capability_arguments,
            *_resource_arguments(handler.support_resources),
            "--script",
            str(script),
        ]
        status, diagnostics = _run(
            command, prepared.environment, timeout_seconds, canonical
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
            response = json.loads(response_file.read_text(encoding="utf-8"))
            if (
                not isinstance(response, dict)
                or response.get("kernel_protocol_version") != KERNEL_PROTOCOL_VERSION
            ):
                raise ValueError("unexpected Kernel Protocol version")
            response_status = response.get("status")
            if response_status == "error":
                cause = response.get("cause")
                reason = response.get("message")
                if not isinstance(cause, str) or not isinstance(reason, str):
                    raise ValueError("Kernel error response has no typed cause/message")
                if cause == "runtime_incompatible":
                    facts = RuntimeCompatibilityDetails.model_validate(
                        response.get("runtime_compatibility")
                    )
                    raise RuntimeIssue(
                        "runtime_incompatible",
                        "Installed Aseprite runtime does not meet the Plan Step requirements",
                        RuntimeCompatibilityEvidence(
                            aseprite_version=facts.aseprite_version,
                            lua_version=facts.lua_version,
                            api_version=facts.api_version,
                            required_lua_language=facts.required_lua_language,
                            minimum_api_version=facts.minimum_api_version,
                            missing_capabilities=tuple(facts.missing_capabilities),
                        ),
                        diagnostics,
                    )
                failed_step = response.get("failed_step")
                failed_operation = response.get("failed_operation")
                if failed_step is not None and (
                    type(failed_step) is not int or failed_step < 1
                ):
                    raise ValueError("Kernel error response has invalid failed_step")
                if failed_operation is not None and not isinstance(
                    failed_operation, str
                ):
                    raise ValueError(
                        "Kernel error response has invalid failed_operation"
                    )
                raise RuntimeIssue(
                    "handler_rejected",
                    f"Packaged {handler_name} handler rejected execution",
                    HandlerEvidence(
                        response_path=str(response_file),
                        reason=reason,
                        failed_step=failed_step,
                        failed_operation=failed_operation,
                    ),
                    diagnostics,
                )
            if response_status != "ok":
                raise ValueError("unknown Kernel response status")
            result = response.get("result")
            if not isinstance(result, dict):
                raise TypeError("Kernel success response has no result object")
            if status != 0:
                raise RuntimeIssue(
                    "exit_mismatch",
                    f"Aseprite exited with status {status} despite a success response",
                    ProcessEvidence(executable=str(canonical), exit_status=status),
                    diagnostics,
                )
            return KernelInvocationResult(
                payload=result,
                response_path=str(response_file),
                diagnostics=diagnostics,
            )
        except RuntimeIssue:
            raise
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            if status != 0:
                raise _process_failure(status, canonical, diagnostics) from exc
            raise RuntimeIssue(
                "response_malformed",
                f"Invalid Kernel response: {exc}",
                ResponseEvidence(response_path=str(response_file)),
                diagnostics,
            ) from exc
