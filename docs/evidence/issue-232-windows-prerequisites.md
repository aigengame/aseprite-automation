# Issue #232: real Windows filesystem and ICC prerequisites

## Scope and candidate

This slice starts from milestone #9 integration commit
`08711223425709bbe5357164707c5d5c2b3f8fc6`. It changes only three existing
unlistable-directory fixtures and the testing notes. Production code, the
working POSIX permission path, symlink assertions and supported ICC identities
are unchanged. Slow tests are excluded.

## Direct observations on 2026-10-14

The command shell is native PowerShell 7.6.5. The fixture explicitly starts
Windows `powershell.exe` 5.1.26100.9444. Python is native CPython 3.13.7
(`win32` / `nt`, UTF-8 mode 0), with locked uv dependencies. Native tests use
Windows Aseprite v1.3.18.5 through direct subprocess calls.

Ordinary-token probes both inside and outside the tool sandbox cannot create
file or directory symlinks: Python reports WinError 1314. PowerShell reports
`NewItemSymbolicLinkElevationRequired`. The observed token has no symlink
privilege; the Developer Mode registry flag is absent. No host setting or
privilege was changed. The owner must select an approved process or host before
the genuine symlink families can be accepted. Bash-launcher-only symlinks remain
#229's harness scope.

`chmod(0o333)` leaves a Windows directory listable. A directory-only ACL that
denies the current user `ListDirectory`, with no child inheritance, produces
real Python `PermissionError` / WinError 5 while the known Source stays readable.
The Windows-only fixture uses this observed condition. Independent normal-body
and exceptional-body probes confirm restored access rules and inheritance
protection, a listable directory and unchanged Source bytes. Windows normalizes
the DACL auto-inheritance flag; byte-identical SDDL is not claimed.

The unit fixture's case-only filenames are already equal as Windows Paths, so
they bypass directory enumeration. Its Windows branch now creates two distinct
hardlink entries for the existing unobservable-entry contract. Real symlink
contracts retain symlinks. On macOS/Linux the original filenames and chmod
condition remain.

When started through a Python child, Windows PowerShell can inherit the parent
pwsh module search path. The fixture explicitly imports the Security module from
its own `$PSHOME`; it does not add a shell fallback or global module-path policy.

The admitted 536-byte caller-owned Apple P3 input is available in retained local
Git history: blob `a484af3025b82a9a9a64e4c6a36acd345856a5f7` from commit
`56fcf844066c47fbac92c49cfb3a3dad161d9f6e`. Its complete SHA-256 is
`0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0`.
An ignored local copy was selected explicitly with `SPA_TEST_APPLE_P3_ICC`.
The unchanged helper accepted its exact bytes. Nothing was downloaded, generated,
added to distribution contents or treated as a new ICC identity. The
[#194 decision](issue-194-redistributable-profile.md) remains applicable.

## Focused results

The original unit condition skipped because chmod did not prevent listing.
After the fixture change, the four publication-identity cases report three
passes and one WinError 1314 failure. The unobservable-entry case now passes
its original refusal assertions rather than skipping.

The preview, static export and Apple-profile preservation E2E cases were
executed, not skipped: all three failed. The latter two reach the known
WinError 10038 native capture block (#230). Preview creates its native Source
and reaches CLI failure/cleanup with no structured stdout; its temporary runtime
cleanup also reports WinError 32. Valid prerequisites do not establish those
downstream outcomes. Native fixture creation, Source/Target effects and profile
preservation must be rerun after the related runtime work.

The default pytest temporary root is not listable in this process. Evidence uses
new owned workspace directories instead of changing that root's permissions.
Raw reports, owned probes and the caller input stay under the ignored
`.runtime/issue-232/` directory. Public records omit hostnames, user names,
absolute local paths and security identities.

## Remaining acceptance

#232 remains open while the approved symlink prerequisite and its focused
family evidence are missing. #234 owns complete applicable-suite green,
isolated-wheel/native effects and the separately documented windowed checks.
The non-slow checkpoint for this slice is recorded below when available;
earlier milestone counts remain separate historical observations.
