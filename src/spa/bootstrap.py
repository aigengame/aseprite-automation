"""Composition root for the installed CLI."""

from functools import partial

from spa.access.cli import build_app, run_cli
from spa.adapters.artifact_set import LocalArtifactSets
from spa.adapters.aseprite.aseprite import invoke, invoke_direct, probe
from spa.adapters.files import LocalArtifactFiles, LocalTargetFiles
from spa.adapters.gif import decode_gif
from spa.adapters.icc import verify_icc
from spa.adapters.palette_file import decode_palette_file
from spa.adapters.png import verify_png
from spa.adapters.png_input import decode_png_artifact, decode_png_input
from spa.adapters.sequence_png import decode_sequence_png
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
                artifact_sets=LocalArtifactSets(),
                decode_sequence_png=decode_sequence_png,
                decode_gif=decode_gif,
                verify_png=verify_png,
                verify_icc=verify_icc,
                decode_palette_file=decode_palette_file,
                decode_png_input=decode_png_input,
                decode_png_artifact=decode_png_artifact,
            ),
            FAILURE_CODES,
        ),
        FAILURE_CODES,
    )
