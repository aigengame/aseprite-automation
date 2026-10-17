"""Host-permission fixtures with one call shape on every platform."""

import os
import stat
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import pytest


def _powershell(command: str, parameters: dict[str, str]) -> str:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            'Import-Module "$PSHOME\\Modules\\Microsoft.PowerShell.Security"; '
            + command,
        ],
        env={**os.environ, **parameters},
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    ).stdout.strip()


AccessRight = Literal["list", "read"]

# POSIX mode that removes the right while the owner can still restore it.
_POSIX_DENIED_MODE = {"list": 0o333, "read": 0o000}

# The rule expression differs by right; the rest of the PowerShell text is shared.
_WINDOWS_DENY_RULE = {
    "list": (
        "$rule = [System.Security.AccessControl.FileSystemAccessRule]::new("
        "[System.Security.Principal.WindowsIdentity]::GetCurrent().User, "
        "[System.Security.AccessControl.FileSystemRights]::ListDirectory, "
        "[System.Security.AccessControl.InheritanceFlags]::None, "
        "[System.Security.AccessControl.PropagationFlags]::None, "
        "[System.Security.AccessControl.AccessControlType]::Deny); "
    ),
    "read": (
        "$rule = [System.Security.AccessControl.FileSystemAccessRule]::new("
        "[System.Security.Principal.WindowsIdentity]::GetCurrent().User, "
        "[System.Security.AccessControl.FileSystemRights]::ReadData, "
        "[System.Security.AccessControl.AccessControlType]::Deny); "
    ),
}


@contextmanager
def deny_access(path: Path, right: AccessRight) -> Iterator[None]:
    """Deny one access right on an owned test path; restore the original access.

    This step only denies and restores. A caller that needs proof that the denial
    works for the current process must probe it, as `deny_directory_listing` does.
    """
    if os.name != "nt":
        original_mode = stat.S_IMODE(path.stat().st_mode)
        path.chmod(_POSIX_DENIED_MODE[right])
        try:
            yield
        finally:
            path.chmod(original_mode)
        return
    parameters = {"SPA_TEST_ACL_PATH": str(path)}
    original = _powershell(
        "(Get-Acl -LiteralPath $env:SPA_TEST_ACL_PATH)"
        ".GetSecurityDescriptorSddlForm("
        "[System.Security.AccessControl.AccessControlSections]::Access)",
        parameters,
    )
    try:
        _powershell(
            "$acl = Get-Acl -LiteralPath $env:SPA_TEST_ACL_PATH; "
            + _WINDOWS_DENY_RULE[right]
            + "$acl.AddAccessRule($rule); "
            "Set-Acl -LiteralPath $env:SPA_TEST_ACL_PATH -AclObject $acl",
            parameters,
        )
        yield
    finally:
        _powershell(
            "$acl = Get-Acl -LiteralPath $env:SPA_TEST_ACL_PATH; "
            "$acl.SetSecurityDescriptorSddlForm($env:SPA_TEST_ACL_SDDL, "
            "[System.Security.AccessControl.AccessControlSections]::Access); "
            "Set-Acl -LiteralPath $env:SPA_TEST_ACL_PATH -AclObject $acl",
            {**parameters, "SPA_TEST_ACL_SDDL": original},
        )


@contextmanager
def deny_directory_listing(directory: Path) -> Iterator[None]:
    """Deny listing on an owned test directory; skip if this process can still list."""
    with deny_access(directory, "list"):
        try:
            os.listdir(directory)
        except PermissionError:
            pass
        else:
            pytest.skip("cannot reproduce an unlistable directory")
        yield


def directory_junction(link: Path, target: Path) -> None:
    """Supply a junction only where directory alias observations are equivalent."""
    assert os.name == "nt", "this fixture is private to Windows tests"
    _powershell(
        'Import-Module "$PSHOME\\Modules\\Microsoft.PowerShell.Management"; '
        "$null = New-Item -ItemType Junction -Path $env:SPA_TEST_JUNCTION_LINK "
        "-Target $env:SPA_TEST_JUNCTION_TARGET",
        {"SPA_TEST_JUNCTION_LINK": str(link), "SPA_TEST_JUNCTION_TARGET": str(target)},
    )


@contextmanager
def symlink_creation_permission() -> Iterator[None]:
    """Keep a genuine Windows creation failure visible as a case-local skip.

    Other platforms need no permission, so errors there pass through unchanged.
    """
    try:
        yield
    except OSError as error:
        if os.name != "nt" or getattr(error, "winerror", None) != 1314:
            raise
        pytest.skip("Windows process cannot create a real symlink (WinError 1314)")
