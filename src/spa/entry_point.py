"""Text stream policy shared by the CLI and optional MCP process entries."""

import sys
from io import TextIOWrapper


def configure_stdio() -> None:
    """Use UTF-8 at process entry, retaining each stream's error policy."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors=stream.errors)
