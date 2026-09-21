"""Atomic Target Commit behavior for Sprite mutation."""

import os
from pathlib import Path

import pytest

from spa.file_adapter import LocalTargetFiles


def test_success_has_no_fallible_checks_after_atomic_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = tmp_path / "staged.aseprite"
    target = tmp_path / "target.aseprite"
    staged.write_bytes(b"sprite")
    replaced = False
    original_replace = os.replace
    original_stat = Path.stat

    def replace(source: Path, destination: Path) -> None:
        nonlocal replaced
        original_replace(source, destination)
        replaced = True

    def stat(path: Path, *args: object, **kwargs: object):
        if replaced and path == target:
            raise OSError("post-commit observation failed")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(Path, "stat", stat)

    committed = LocalTargetFiles().commit(staged, target)

    assert committed.target_sprite_file == str(target)
    assert committed.byte_size == len(b"sprite")
    assert replaced is True
