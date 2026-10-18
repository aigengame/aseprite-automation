"""Native executable entries made from a Python body on every platform."""

import os
import sys
from pathlib import Path


def python_entry(directory: Path, name: str, body: str) -> Path:
    """Write a Python body as an entry that a caller can start by its path.

    Windows wraps the body in a native distlib launcher. Other platforms use the
    body file itself, with a shebang line for the current interpreter.
    """
    if os.name == "nt":
        from distlib.scripts import ScriptMaker

        source = directory / f"{name}-source"
        source.mkdir(parents=True)
        (source / f"{name}.py").write_text(
            "#!python\n" + body, encoding="utf-8", newline="\n"
        )
        ScriptMaker(str(source), str(directory)).make(f"{name}.py")
        return directory / f"{name}.exe"
    directory.mkdir(parents=True, exist_ok=True)
    entry = directory / name
    entry.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    entry.chmod(0o755)
    return entry
