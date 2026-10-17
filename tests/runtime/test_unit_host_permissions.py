"""Check the host-permission fixtures that every test platform shares."""

import os
from pathlib import Path

import pytest

from tests.host_permissions import (
    deny_access,
    deny_directory_listing,
    symlink_creation_permission,
)

pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="the Windows ACL path needs a native Windows run"
)


def test_symlink_permission_passes_other_errors_through() -> None:
    with pytest.raises(OSError, match="plain failure"), symlink_creation_permission():
        raise OSError("plain failure")


def test_directory_listing_denial_restores_access(tmp_path: Path) -> None:
    private = tmp_path / "private"
    private.mkdir()
    (private / "entry").write_text("x", encoding="utf-8")
    mode = private.stat().st_mode
    with deny_directory_listing(private), pytest.raises(PermissionError):
        os.listdir(private)
    assert private.stat().st_mode == mode
    assert os.listdir(private) == ["entry"]


def test_directory_listing_denial_restores_access_after_failure(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    private.mkdir()
    with (
        pytest.raises(RuntimeError, match="body failed"),
        deny_directory_listing(private),
    ):
        raise RuntimeError("body failed")
    assert os.listdir(private) == []


def test_read_denial_restores_access(tmp_path: Path) -> None:
    file = tmp_path / "data.bin"
    file.write_bytes(b"payload")
    with deny_access(file, "read"), pytest.raises(PermissionError):
        file.read_bytes()
    assert file.read_bytes() == b"payload"


def test_read_denial_restores_access_after_failure(tmp_path: Path) -> None:
    file = tmp_path / "data.bin"
    file.write_bytes(b"payload")
    with pytest.raises(RuntimeError, match="body failed"), deny_access(file, "read"):
        raise RuntimeError("body failed")
    assert file.read_bytes() == b"payload"
