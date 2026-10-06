"""Application entry point for exact caller-owned Lua, outside Operation Plans."""

from spa.contracts.caller_script import (
    ScriptRunRequest,
    ScriptRunResult,
    ScriptSuccessDiagnostics,
)
from spa.contracts.operation import RUNTIME_FAILURE_CODES, OperationDescriptor
from spa.contracts.ports import OperationServices
from spa.contracts.public import RuntimeRequirements


def run_script(
    request: ScriptRunRequest, services: OperationServices
) -> ScriptRunResult:
    if services.invoke_script is None:
        raise RuntimeError("Caller-script adapter is not configured")
    observed = services.invoke_script(services.probe_runtime(request), request)
    return ScriptRunResult(
        executable=observed.executable,
        working_directory=observed.working_directory,
        timeout_seconds=request.timeout_seconds,
        output_limit_bytes=observed.output_limit_bytes,
        diagnostics=ScriptSuccessDiagnostics.model_validate(
            observed.diagnostics.model_dump()
        ),
        files=list(observed.files),
    )


SCRIPT_OPERATIONS = (
    OperationDescriptor(
        "script run",
        ScriptRunRequest,
        ScriptRunResult,
        run_script,
        lambda result: (
            f"Caller script process exited with status {result.diagnostics.exit_status}"
        ),
        RuntimeRequirements(
            lua_language="Lua 5.4",
            minimum_api_version=41,
            required_capabilities=["aseprite_runtime_introspection"],
        ),
        RUNTIME_FAILURE_CODES,
        execution_kind="script-run",
        determinism="caller-defined",
        side_effects=("caller-defined",),
        help_summary="Run exact caller-owned Lua; success reports process facts only.",
    ),
)
