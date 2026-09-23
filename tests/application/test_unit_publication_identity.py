"""File observations used by Source/Target publication intent."""

import os
from pathlib import Path

import pytest

from spa.file_adapter import LocalTargetFiles
from spa.mutation import source_target_identity_issue


def test_case_variant_names_identify_one_existing_publication_entry(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Sprite.aseprite"
    source.write_bytes(b"source")
    target = tmp_path / "sprite.aseprite"
    if not target.exists():
        pytest.skip("requires a case-insensitive filesystem")

    files = LocalTargetFiles()
    assert files.same_publication_entry(source, target)
    assert files.same_publication_target(source, target)
    assert source_target_identity_issue(files, source, target, False) is not None
    assert source_target_identity_issue(files, source, target, True) is None


def test_distinct_hard_links_are_distinct_publication_entries(tmp_path: Path) -> None:
    source = tmp_path / "source.aseprite"
    source.write_bytes(b"source")
    target = tmp_path / "target.aseprite"
    os.link(source, target)

    files = LocalTargetFiles()
    assert source.samefile(target)
    assert not files.same_publication_entry(source, target)
    assert not files.same_publication_target(source, target)


def test_case_variant_source_alias_traverses_target_entry(tmp_path: Path) -> None:
    target = tmp_path / "Sprite.aseprite"
    target.write_bytes(b"target")
    spelling = tmp_path / "sprite.aseprite"
    if not spelling.exists():
        pytest.skip("requires a case-insensitive filesystem")
    source = tmp_path / "alias.aseprite"
    source.symlink_to(spelling)

    files = LocalTargetFiles()
    assert not files.same_publication_entry(source, target)
    assert files.same_publication_target(source, target)
    for in_place in (False, True):
        issue = source_target_identity_issue(files, source, target, in_place)
        assert issue is not None
        assert issue.location == ["source_sprite_file"]


def test_unobservable_entries_reject_both_in_place_intents(tmp_path: Path) -> None:
    parent = tmp_path / "private"
    parent.mkdir()
    source = parent / "Sprite.aseprite"
    source.write_bytes(b"source")
    target = parent / "sprite.aseprite"
    if not target.exists():
        os.link(source, target)

    parent.chmod(0o333)
    try:
        try:
            os.listdir(parent)
        except PermissionError:
            pass
        else:
            pytest.skip("cannot reproduce an unlistable directory")
        for in_place in (False, True):
            issue = source_target_identity_issue(
                LocalTargetFiles(), source, target, in_place
            )
            assert issue is not None
            assert issue.location == ["source_sprite_file"]
    finally:
        parent.chmod(0o700)
