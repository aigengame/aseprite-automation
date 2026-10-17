"""Private Windows entry for fixtures selected by executable path."""

import os
from pathlib import Path


def windows_aseprite(tmp_path: Path, body: str) -> Path:
    """Wrap a Python fixture body in a native entry with the existing resource layout."""
    assert os.name == "nt"
    from distlib.scripts import ScriptMaker

    source = tmp_path / "windows-script"
    source.mkdir(parents=True)
    (source / "aseprite.py").write_text(
        "#!python\nimport sys\n"
        "sys.stdout.reconfigure(encoding='utf-8', newline='\\n')\n"
        "sys.stderr.reconfigure(encoding='utf-8', newline='\\n')\n" + body + "\n",
        encoding="utf-8",
        newline="\n",
    )
    directory = tmp_path / "Aseprite.app" / "Contents" / "MacOS"
    maker = ScriptMaker(str(source), str(directory))
    maker.make("aseprite.py")
    resource = directory.parent / "Resources" / "data" / "gui.xml"
    resource.parent.mkdir(parents=True)
    resource.write_text("<gui/>", encoding="utf-8")
    return directory / "aseprite.exe"
