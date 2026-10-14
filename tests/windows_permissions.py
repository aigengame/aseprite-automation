"""Windows-only setup for existing unlistable-directory observations."""

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _powershell(command: str, directory: Path, sddl: str = "") -> str:
    environment = {
        **os.environ,
        "SPA_TEST_ACL_DIRECTORY": str(directory),
        "SPA_TEST_ACL_SDDL": sddl,
    }
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
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=10,
    ).stdout.strip()


@contextmanager
def deny_directory_listing(directory: Path) -> Iterator[None]:
    """Deny listing only on an owned test directory; restore its access rules."""
    assert os.name == "nt", "this fixture is private to Windows tests"
    original = _powershell(
        "(Get-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY)"
        ".GetSecurityDescriptorSddlForm("
        "[System.Security.AccessControl.AccessControlSections]::Access)",
        directory,
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
            directory,
        )
        yield
    finally:
        _powershell(
            "$acl = Get-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY; "
            "$acl.SetSecurityDescriptorSddlForm($env:SPA_TEST_ACL_SDDL, "
            "[System.Security.AccessControl.AccessControlSections]::Access); "
            "Set-Acl -LiteralPath $env:SPA_TEST_ACL_DIRECTORY -AclObject $acl",
            directory,
            original,
        )
