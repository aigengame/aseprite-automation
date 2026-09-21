"""Composition root for the installed CLI."""

from spa.cli import build_app, run_cli
from spa.failure_registry import FAILURE_CODES
from spa.file_adapter import LocalTargetFiles
from spa.ports import OperationServices
from spa.runtime.aseprite import invoke, probe


def main() -> None:
    run_cli(
        build_app(
            OperationServices(
                probe_runtime=probe,
                invoke_kernel=invoke,
                target_files=LocalTargetFiles(),
            ),
            FAILURE_CODES,
        ),
        FAILURE_CODES,
    )
