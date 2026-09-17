"""Composition root for the installed CLI."""

from spa.cli import build_app, run_cli
from spa.runtime.aseprite import probe


def main() -> None:
    run_cli(build_app(probe))
