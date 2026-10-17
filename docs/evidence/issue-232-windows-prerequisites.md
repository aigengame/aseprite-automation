# Issue #232: real Windows filesystem and ICC prerequisites

This historical record covers [PR #245](https://github.com/aigengame/aseprite-automation/pull/245),
merged as `2063272b8caa1fca4cb1c3401db9ac9b2b38bb6e`, and later references
[PR #266](https://github.com/aigengame/aseprite-automation/pull/266), merged as
`ad07fb4a42b13cf78a572c634e376664cc130f2d`. Source IDs retain their pre-merge
measurements. Current delivery status belongs to
[#232](https://github.com/aigengame/aseprite-automation/issues/232).

Here, an ordinary token means a non-elevated Windows process. A capable process
means a separately approved temporary administrator process that can create real
symlinks. A witness is an executed probe or test with its recorded result; its
name does not establish a support promise.

## Scope and candidate

This slice starts from milestone #9 integration commit
`08711223425709bbe5357164707c5d5c2b3f8fc6`. The first increment supplies three
existing unlistable-directory fixtures. The next increment adds a proven
directory-junction witness and case-local Windows symlink-permission reporting
to two existing Source fixtures. The last increment applies the same reporting
at the remaining creation sites demonstrated by 29 non-Bash nodes, in 13
existing test files. Production code, working POSIX fixtures,
Source alias inputs and supported ICC identities are unchanged. Slow tests are
excluded. The checkpoints below have separate candidate identities.

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
`.runtime/issue-232/` directory. These raw files exist only on the measuring host.
Public records omit hostnames, user names,
absolute local paths and security identities.

## Initial complete non-slow checkpoint

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
after the run.

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
#234 retains the final applicable-test gate. No new skip was added in this
initial candidate.

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
All 78 pass on the unchanged ordinary Windows token. At that experiment the
original tracked tests and their file hashes were unchanged. The 4,470-node checkpoint above
is unchanged; these experimental passes are not added to it.

The 13 excluded alias witnesses comprise five successful caller observations,
five Source-retarget failures and three pre-native alias refusals. They remain
real symlink observations. The counterfactual does not establish alias reading,
retarget detection, original-target preservation or Aseprite reading an alias.
The other 30 non-Bash observations have not been reclassified by this experiment.

The ordinary-Source proposal was not selected after the owner's gda reference.
The current increment retains all original Source alias inputs and assertions.
The experiment is a necessity investigation, not a coverage replacement. Do not
replace symlinks with hardlinks, label shared semantics Unix-only, add blanket
skips, introduce a permission broker, or impose a host setting to turn this
experiment into an apparent pass.

Raw counterfactual XML, original-node mapping and hashes are retained in
`.runtime/issue-232/ordinary-source-counterfactual/`. Independent review traced
the fixtures to the PNG publication baseline (#142/#138) and Snapshot
publication work (#180/#179); it confirms the evidence limit and the need to
preserve alias coverage during any split.

## gda boundary adopted in the first increment

The [gda helper](https://github.com/aigengame/godot-agent/blob/43d973b4ccf1e5193a48d6819d61cbbe7cb93022/tests/support.py#L649-L658)
only skips the current case for Windows WinError 1314; other creation errors
remain errors. Its [#1157 classification](https://github.com/aigengame/godot-agent/issues/1157)
uses junctions only for equivalent directory identity/ownership observations.
Its [#1182 temporary-process record](https://github.com/aigengame/godot-agent/issues/1182#issuecomment-6108581494)
reports 12 ordinary skips separately from 12 passes under an explicitly approved
temporary administrator process. That approval does not authorize a SPA process.

SPA's first increment follows those boundaries:

- One existing Convolution directory-alias test uses a Windows-private junction
  fixture through `powershell.exe`. The actual junction is checked with
  `is_junction()` and `samefile()`. The original repeated-resource load,
  canonical Source paths and duplicate-name assertions all pass. No symlink-type,
  relative-target, retarget, cycle, deletion or `link/..` equivalence is claimed.
  The POSIX symlink setup stays in place.
- The two shared publication fixtures retain every original Source symlink
  input. Only their Windows branch wraps the existing Python creation call in
  a private permission observation. A genuine 1314 becomes a current-case
  prerequisite skip; any other `OSError` is raised. This does not supply another
  creator, intercept a product API, skip a whole module or migrate POSIX callers.
- Focused ordinary-process results: **94 = 3 passed / 91 prerequisite skipped**.
  The passes are the directory-alias case, the existing denial-unit case and the
  existing ordinary Tilemap summary. The 91 cases do not reach their functional
  assertions. They are unavailable observations, not fixed or accepted outcomes.
- The PowerShell invocation adjustment also passed real normal-body and
  exceptional-body ACL restoration witnesses. No host policy was changed.

At this first increment, the remaining genuine alias sites had not received
this permission handling. The bounded evidence run can use the 121 existing non-Bash observation
nodes from the frozen checkpoint, in a temporary approved Windows process.
It must preserve any downstream native or fixture failure, use fresh owned
outputs, and report ordinary and elevated receipts separately. No whole-suite
elevation or persistent Developer Mode/registry/privilege-policy change follows.

The [gda #1199 record](https://github.com/aigengame/godot-agent/pull/1199#issuecomment-6158833540)
still has three permission skips in an ordinary process at its measured revision.
A temporary successful witness never grants the next ordinary process rights.

## Complete non-slow checkpoint after the gda increment

Source `91369fcdee5e4b9cedaee60d071948d0a6429cef` selected the same 4,470
existing non-slow nodes. All four native worker inventories agree; every node
has exactly one JUnit outcome. Two slow rebuilds were deselected. Exit status
is 1. Elapsed driver time is 347.6 seconds.

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,140 | 12 | 0 | 40 | 1,192 |
| Integration | 657 | 136 | 0 | 98 | 891 |
| E2E | 52 | 1,285 | 1,049 | 1 | 2,387 |
| Total | **1,849** | **1,433** | **1,049** | **139** | **4,470** |

Compared with candidate `15369ae`, the proven directory-junction case accounts
for one additional pass and one fewer failure. The 91 Source-fixture setup
errors become explicit WinError 1314 prerequisite skips. Those cases still do
not reach functional assertions; no 91-case repair is claimed. The other 48
skip reasons remain as recorded in the initial checkpoint. The counterfactual
78 passes are not included in either checkpoint.

There are 131 WinError 1314 observations: the 91 explicit skips plus 40 remaining
failures. Of the latter, 29 are non-Bash nodes whose genuine symlink sites have
not received case-local permission reporting yet; the other 11 obsolete
Bash-launcher nodes remain #229 scope. Capture WinError 10038 still appears in
2,187 nodes. Audit-only hooks refuse 63 excluded-shell attempts at the inspected
project and candidate-wheel Python call points. These counts overlap and do not
predict post-fix passes. No excluded shell is supplied as a fallback.

The candidate wheel was rebuilt and installed into a fresh locked uv consumer.
Its bytes match the initial wheel because this increment changes tests and
documentation. The existing installed-CLI verifier passes outside the checkout
and matches all 145 Kernel resource hashes when run outside the tool filesystem
sandbox under the ordinary Windows token. The sandbox attempt fails at the uv
launcher path gate and is retained separately; it is not counted as a native
Windows product failure. Audit-hook registrations were removed from both Python
environments. No Aseprite survivor whose command line contains the owned
checkpoint root was observed. These bounded harness checks do not establish
production cleanup or native wheel effects.

- JUnit SHA-256: `0df5732cf0458597bd7f419236c2b33df0a60ecad39b981a914ca199502ef77a`.
- Candidate wheel SHA-256: `0e9f1256aaaf2ba9c4d46fa70e369ba7dffd0bc7bb6c0ca6b57d0f56294262aa`.
- Raw XML, per-node outcomes, matching worker inventories, node evidence and
  launch trace remain in `.runtime/issue-232/gda-checkpoint/`. The installed
  verifier logs and real ACL-lifecycle receipts remain alongside that directory.

Independent Standards and Spec reviews of `91369fc` against `bcc8156`
report no actionable defect or scope expansion. They retain the incomplete
alias evidence and unadapted sites as incomplete acceptance.

## Approved temporary-process witness

The owner explicitly approved one temporary UAC validation process for the
frozen test revision `91369fc`. Its selection is the original 121 non-Bash
observation nodes: the 91 retained Source-fixture cases, the 29 other symlink
observations and the junction case as a control. This is an evidence selection,
not a claim that every selected contract needs a symlink. No slow node or
Bash-launcher node is included. The process first creates real file and
directory symlinks and checks their types, identity and unchanged Source bytes.
Both probes succeed. The unchanged existing tests then report:

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 53 | 0 | 0 | 0 | 53 |
| Integration | 61 | 0 | 0 | 0 | 61 |
| E2E | 0 | 7 | 0 | 0 | 7 |
| Total | **114** | **7** | **0** | **0** | **121** |

Exit status is 1; elapsed driver time is 20.02 seconds. Every selected node has
one outcome, and none reports WinError 1314. These results are separate from
the ordinary-process full checkpoint; do not add 114 passes to its totals.

| Existing failed node | First visible boundary | Existing owner |
| --- | --- | --- |
| Animation `test_preview_rejects_destination_traversed_by_source_alias` | Runtime probe capture WinError 10038, then cleanup WinError 32 | #230 |
| Paint `test_apply_accepts_in_place_paths_to_the_same_publication_entry` | Initial Source creation CLI exits 1 with empty stdout; alias assertion not reached | #230 diagnosis/rerun |
| Runtime `test_symlinked_executable_resolves_to_resource_complete_bundle` | `spa info` exits 1 with empty stdout | #230 diagnosis/rerun |
| Selection `test_artifact_input_alias_is_not_replaced[absolute-symlink-export]` | CLI stdout cannot be read as JSON | #230 diagnosis/rerun |
| Selection `test_artifact_input_alias_is_not_replaced[absolute-symlink-preview]` | CLI stdout cannot be read as JSON | #230 diagnosis/rerun |
| Selection `test_artifact_input_alias_is_not_replaced[tilde-symlink-export]` | After real symlink creation, home-relative input construction raises cross-volume `ValueError` before SPA | #243 |
| Selection `test_artifact_input_alias_is_not_replaced[tilde-symlink-preview]` | Same existing input-construction boundary | #243 |

The last two cases share #243's existing `relpath(source, Path.home())` fixture
with the two direct-input cases. Include all four evidenced home-relative
variants in that correction; introduce no product path feature. Keep real
symlink provisioning under #232 and file-preservation/refusal assertions intact.
The four native-entry failures without complete stderr are not all diagnosed
as WinError 10038; follow their actual next boundary during #230 work.

Independent Spec review confirms these boundaries and existing ownership.
No new issue or production mechanism follows from the witness. The temporary
process has exited. A subsequent ordinary-token file/directory probe again
reports WinError 1314; its original bytes remain unchanged. The ordinary token
is not administrative, the Developer Mode flag remains absent, and no Aseprite
survivor with the owned witness root or unobservable Aseprite command line is
observed. No Developer Mode, registry or privilege policy was changed. This
does not grant future ordinary processes permission or establish #234 acceptance.

- Witness JUnit SHA-256: `a493b196f31aaa0fb119974e6ee8cb4064f022cad815b60a1a125ebec6ef26fe`.
- Frozen node-list SHA-256: `0d580ceb37ce0eab45895837638707ae78141655f39c1ca849736a57ce24d555`.
- The local manifest, receipt, XML, per-node outcomes and launch trace remain in
  the single ignored `.runtime/issue-232/temporary-witness-*/` output. The
  post-witness ordinary probe and bounded process check remain alongside it.

## Latest ordinary-process fixture checkpoint

Source `68eb2da7c5ce468a60870783cb2af4c36087ada3` adds Windows-private
permission observations only at the remaining demonstrated creation sites.
The original POSIX calls and all input, retarget, type, byte-preservation and
CLI assertions remain. No further junction or product mechanism is added.

The ordinary 121-node selection now reports **1 passed / 120 WinError 1314
prerequisite skips**. The pass is the existing junction control. Ruff check
and formatting pass for all 13 changed files; diff checks pass. Static AST
comparison confirms unchanged existing POSIX execution bodies, excluding
imports; macOS/Linux were not executed here. Independent Standards and
Spec reviews report no actionable defect or scope expansion.

The complete ordinary-process checkpoint again reconciles all four worker
inventories and one outcome per selected node. Exit status is 1, driver time
358.43 seconds, and the two slow rebuilds are deselected.

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,140 | 0 | 0 | 52 | 1,192 |
| Integration | 657 | 126 | 0 | 108 | 891 |
| E2E | 52 | 1,278 | 1,049 | 8 | 2,387 |
| Total | **1,849** | **1,404** | **1,049** | **168** | **4,470** |

Compared with `91369fc`, the 29 demonstrated failures become current-case
permission skips. There is no new functional pass. All 120 genuine symlink
observations remain unavailable under this ordinary token; the other 48 skips
retain their recorded reasons. The 11 remaining WinError 1314 failures are
obsolete Bash-launcher fixtures under #229. Retain the separately recorded
114 passes and seven failures from the earlier approved `91369fc` witness;
it is not an elevated execution of this newer test revision.

The existing candidate wheel is reused for this tests-only increment: source
package contents and locked dependencies are unchanged. Its verified 145-resource
receipt is not a new native wheel-effect pass. Raw XML, exact outcomes,
matching collections, launch trace, node evidence and cleanup receipt remain in
`.runtime/issue-232/permission-checkpoint/`.
Capture WinError 10038 remains at 2,187 overlapping nodes; the 63 excluded-shell
attempts remain refused and owned by #229. Audit registrations were removed,
and the bounded post-run process query finds no owned Aseprite survivor or
unobservable Aseprite command line.

- JUnit SHA-256: `b8f1ffadf842b67af0a128e5148d5209ce70c9b9854d4eddc7536dfe36892f77`.

## Disposition recorded on 2026-10-17

The checkpoints above retain their original revisions and outcomes. Issue #232
was completed through [PR #266](https://github.com/aigengame/aseprite-automation/pull/266).
The [Windows integration measurements (#234)](issue-234-windows-acceptance.md) record
the integrated results, separate capable-process symlink witnesses, installed
wheel evidence, and real windowed comparisons owned by #234.

Case-local reporting does not grant the ordinary token symlink permission.
All approved temporary witnesses have exited; their authorization does not
carry to another process. No host-setting or further elevation decision is
pending. The owner-deferred #230 investigation remains unresolved and
non-blocking; these historical failures are not current failure counts.
