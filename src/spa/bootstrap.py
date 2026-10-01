"""Composition root for the installed CLI."""

from functools import partial

from spa.access.cli import build_app, run_cli
from spa.adapters.aseprite.aseprite import invoke, invoke_direct, probe
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.icc import verify_icc
from spa.adapters.png import verify_png
from spa.application.failure_registry import FAILURE_CODES
from spa.application.surface import PROBE_RESOURCES
from spa.contracts.ports import OperationServices


def main() -> None:
    run_cli(
        build_app(
            OperationServices(
                probe_runtime=partial(probe, resources=PROBE_RESOURCES),
                invoke_kernel=invoke,
                invoke_kernel_direct=invoke_direct,
                target_files=LocalTargetFiles(),
                artifact_files=LocalArtifactFiles(),
                verify_png=verify_png,
                verify_icc=verify_icc,
            ),
            FAILURE_CODES,
        ),
        FAILURE_CODES,
    )
