"""Windows-only setup for existing filesystem observations."""

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

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


@contextmanager
def deny_directory_listing(directory: Path) -> Iterator[None]:
    """Deny listing only on an owned test directory; restore its access rules."""
    assert os.name == "nt", "this fixture is private to Windows tests"
    parameters = {"SPA_TEST_ACL_DIRECTORY": str(directory)}
    original = _powershell(
        "(Get-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY)"
        ".GetSecurityDescriptorSddlForm("
        "[System.Security.AccessControl.AccessControlSections]::Access)",
        parameters,
    )
    try:
        _powershell(
            "$acl = Get-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY; "
            "$rule = [System.Security.AccessControl.FileSystemAccessRule]::new("
            "[System.Security.Principal.WindowsIdentity]::GetCurrent().User, "
            "[System.Security.AccessControl.FileSystemRights]::ListDirectory, "
            "[System.Security.AccessControl.InheritanceFlags]::None, "
            "[System.Security.AccessControl.PropagationFlags]::None, "
            "[System.Security.AccessControl.AccessControlType]::Deny); "
            "$acl.AddAccessRule($rule); "
            "Set-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY -AclObject $acl",
            parameters,
        )
        yield
    finally:
        _powershell(
            "$acl = Get-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY; "
            "$acl.SetSecurityDescriptorSddlForm($env:SPA_TEST_ACL_SDDL, "
            "[System.Security.AccessControl.AccessControlSections]::Access); "
            "Set-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY -AclObject $acl",
            {**parameters, "SPA_TEST_ACL_SDDL": original},
        )


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
    """Keep a genuine creation failure visible as a case-local prerequisite skip."""
    assert os.name == "nt", "this observation is private to Windows tests"
    try:
        yield
    except OSError as error:
        if getattr(error, "winerror", None) != 1314:
            raise
        pytest.skip("Windows process cannot create a real symlink (WinError 1314)")
