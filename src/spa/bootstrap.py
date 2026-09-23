"""Composition root for the installed CLI."""

from functools import partial

from spa.cli import build_app, run_cli
from spa.export import EXPORT_PROBE_RESOURCES
from spa.failure_registry import FAILURE_CODES
from spa.file_adapter import LocalArtifactFiles, LocalTargetFiles
from spa.ports import OperationServices
from spa.runtime.aseprite import invoke, probe
from spa.sprite import SPRITE_PROBE_RESOURCES


def main() -> None:
    run_cli(
        build_app(
            OperationServices(
                probe_runtime=partial(
                    probe, resources=(*SPRITE_PROBE_RESOURCES, *EXPORT_PROBE_RESOURCES)
                ),
                invoke_kernel=invoke,
                target_files=LocalTargetFiles(),
                artifact_files=LocalArtifactFiles(),
            ),
            FAILURE_CODES,
        ),
        FAILURE_CODES,
    )
