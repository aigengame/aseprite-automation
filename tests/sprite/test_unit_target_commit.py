"""Atomic Target Commit behavior for Sprite mutation."""

import os
from pathlib import Path

import pytest

from spa.adapters.files import LocalTargetFiles
from spa.contracts.ports import RuntimeIssue


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

    committed = LocalTargetFiles().commit(staged, target, overwrite=True)

    assert committed.target_sprite_file == str(target)
    assert committed.byte_size == len(b"sprite")
    assert replaced is True


def test_existing_target_is_preserved_without_explicit_overwrite(
    tmp_path: Path,
) -> None:
    staged = tmp_path / "staged.aseprite"
    target = tmp_path / "target.aseprite"
    staged.write_bytes(b"new")
    target.write_bytes(b"existing")

    with pytest.raises(RuntimeIssue) as failure:
        LocalTargetFiles().commit(staged, target, overwrite=False)

    assert failure.value.kind == "target_commit_failed"
    assert failure.value.evidence.reason == "overwrite_not_allowed"
    assert target.read_bytes() == b"existing"
    assert staged.read_bytes() == b"new"


def test_existing_target_is_replaced_with_explicit_overwrite(tmp_path: Path) -> None:
    staged = tmp_path / "staged.aseprite"
    target = tmp_path / "target.aseprite"
    staged.write_bytes(b"new")
    target.write_bytes(b"existing")

    committed = LocalTargetFiles().commit(staged, target, overwrite=True)

    assert committed.target_sprite_file == str(target)
    assert target.read_bytes() == b"new"
