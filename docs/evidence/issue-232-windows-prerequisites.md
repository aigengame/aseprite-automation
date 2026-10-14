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
privilege was changed. This records the selected process's creation capability;
it does not establish a Developer Mode requirement for every developer host.
Classify the fixture dependency before selecting an acceptance environment for
the actual alias observations. Bash-launcher-only symlinks remain #229 scope.
The [Win32 symlink API](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createsymboliclinkw)
documents Developer Mode as a prerequisite for its unprivileged creation flag.

`chmod(0o333)` leaves a Windows directory listable. A directory-only ACL that
denies the current user `ListDirectory`, with no child inheritance, produces
real Python `PermissionError` / WinError 5 while the known Source stays readable.
The Windows-only fixture uses this observed condition. Independent normal-body
and exceptional-body probes confirm restored access rules and inheritance
protection, a listable directory and unchanged Source bytes. Windows normalizes
the DACL auto-inheritance flag; byte-identical SDDL is not claimed.
The [Windows rights reference](https://learn.microsoft.com/en-us/dotnet/api/system.security.accesscontrol.filesystemrights)
defines `ListDirectory` separately from the other access rights.

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

## Complete non-slow checkpoint

Source `15369aede47fc31ef3a4ad55ae0d35875b8af377` selected all 4,470 existing
non-slow nodes with four native pytest workers. All worker collections agree,
and every selected node has exactly one JUnit outcome. The two slow rebuilds
were deselected. Exit status is 1; this is a failure checkpoint, not acceptance.

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,139 | 13 | 40 | 0 | 1,192 |
| Integration | 657 | 136 | 51 | 47 | 891 |
| E2E | 52 | 1,285 | 1,049 | 1 | 2,387 |
| Total | **1,848** | **1,434** | **1,140** | **48** | **4,470** |

The existing denial-unit case passes. The existing preview and Apple-profile
preservation cases are failures, with no prerequisite skip. Static export still
fails before its directory observation at native capture. These are reached
boundaries, not predictions about later domain assertions.

There are 132 WinError 1314 observations: 121 non-Bash filesystem setup
observations remain #232 scope; the 11 Bash-launcher-only cases remain #229 scope.
The 121 count does not establish 121 independently necessary alias contracts.
There are
2,187 nodes with capture WinError 10038 evidence. Counts overlap and are not
independent defects or promised post-fix passes. Native execution/cleanup remains
#230 scope. The 63 explicit excluded-shell attempts are refused before process
creation by audit-only hooks in the project and candidate-wheel Python
environments; their harness failures remain #229 scope. The hooks were removed
after the run. This is not an OS-wide process security claim.

The 48 remaining skip reasons are retained, not reclassified as passes:

| Existing reason | Nodes |
| --- | ---: |
| POSIX process fixture | 26 |
| POSIX executable fixture | 10 |
| POSIX shell fixture | 4 |
| POSIX signal fixture | 2 |
| Process-group cleanup on supported macOS/Linux hosts | 2 |
| macOS bundle launch strategy | 2 |
| POSIX pipe fixture | 1 |
| Installed Aseprite in a macOS agent sandbox | 1 |

Fixture labels do not establish platform applicability. Existing milestone
issues own the Windows observations and true POSIX/macOS-only classification;
#234 retains the final applicable-test gate. No new skip was added here.

The candidate wheel was built from the same source and installed with locked
runtime/MCP dependencies into a separate uv environment. The existing installed
CLI verifier passed outside the checkout and matched all 145 Kernel resource
hashes. This does not establish native wheel effects. The selected paths were
local inputs, not repository defaults. No survivor whose Aseprite command line
contained the owned checkpoint root was observed after the run; this bounded
harness observation is not production cleanup acceptance.

- JUnit SHA-256: `bafa81c08c742339d91aa885a5e9146f9d85b0482c21ad6bd0c6476c2c3832ab`.
- Candidate wheel SHA-256: `0e9f1256aaaf2ba9c4d46fa70e369ba7dffd0bc7bb6c0ca6b57d0f56294262aa`.
- Raw XML, per-node outcomes, matching worker inventories, launch trace and hashes
  remain in `.runtime/issue-232/checkpoint/`; the installed verifier log and
  ACL-lifecycle evidence remain alongside that directory.

Earlier 4,470-node and closed-PR #242 results remain separate histories. The
closed branch's additional test splits were not merged into this candidate.

## Fixture dependency review - 2026-10-14

The owner challenged the recommendation to enable Developer Mode. That
recommendation is withdrawn. No host change was approved or made. Developer
Mode is an OS permission option, not a SPA runtime or general development
prerequisite. A test environment that must create genuine symlinks still needs
the corresponding Windows capability; changing a Python fixture cannot remove
that OS restriction.

Two common Source-symlink fixtures cause 91 setup observations. Their inputs
also cover ordinary publication, failure order and cleanup:

| Existing module | Observations | Ordinary-contract counterfactual | Retained alias witnesses |
| --- | ---: | ---: | ---: |
| `tests/delivery/test_unit_png_callers.py` | 40 | 36 | 4 |
| `tests/delivery/test_integration_snapshot_publication.py` | 51 | 42 | 9 |
| Total | 91 | **78** | **13** |

An ignored-copy experiment changes only the initial Source fixture to the
ordinary original file, selects those 78 nodes, and forbids symlink creation.
All 78 pass on the unchanged ordinary Windows token. Original tracked tests
and their file hashes remain unchanged. The full 4,470-node checkpoint above
is unchanged; these experimental passes are not added to it.

The 13 excluded alias witnesses comprise five successful caller observations,
five Source-retarget failures and three pre-native alias refusals. They remain
real symlink observations. The counterfactual does not establish alias reading,
retarget detection, original-target preservation or Aseprite reading an alias.
The other 30 non-Bash observations have not been reclassified by this experiment.

The bounded recovery proposal is to give the ordinary Windows publication
observations ordinary Source inputs, preserve explicit real alias witnesses
and their Source/Target/cleanup assertions, and leave working POSIX fixtures
in place. This changes Windows input coverage, so it needs owner alignment
before implementation. No test-input change has been delivered yet. Do not
replace symlinks with hardlinks, label their shared semantics Unix-only, add
blanket skips, introduce a permission broker, or impose a host setting to turn
this experiment into an apparent pass.

Raw counterfactual XML, original-node mapping and hashes are retained in
`.runtime/issue-232/ordinary-source-counterfactual/`. Independent review traced
the fixtures to the PNG publication baseline (#142/#138) and Snapshot
publication work (#180/#179); it confirms the evidence limit and the need to
preserve alias coverage during any split.

## Remaining acceptance

#232 remains open while fixture necessity and the retained real alias evidence
are unresolved. There is no pending approval to enable Developer Mode; the next
decision is the bounded Windows fixture-input split. #234 owns complete applicable-suite green,
isolated-wheel/native effects and the separately documented windowed checks.
The checkpoint satisfies the requirement to record all existing non-slow
outcomes; it does not satisfy complete-suite acceptance or the outstanding
real-symlink requirement.
