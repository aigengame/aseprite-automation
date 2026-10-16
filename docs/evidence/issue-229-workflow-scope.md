# Issue 229: Native shared logic and Linux workflow composition

Issue [#229](https://github.com/aigengame/aseprite-automation/issues/229) owns
75 failed harness observations from the complete Windows checkpoint at
`bb5bfe2bc7822602806b48a746cc62c41c575846`, plus one raw pass that caught a
real-`gh` audit refusal instead of executing its controlled producer. These
are test-node observations, not 76 SPA product defects.

The [exact node mapping](issue-229-workflow-scope.json) also identifies all
26 historical mixed-shell passes. Applicability follows each assertion and its
actual implementation. A previous pass does not make a Bash workflow contract a
Windows capability.

| Existing observations | Windows treatment | Preserved applicable-host evidence |
| --- | --- | --- |
| Two hosted release-admission `gh` cases | Execute the authoritative inline Python with a local Windows-only `gh.exe`, exact selection check and actual API receipts. | Existing POSIX fixture execution. |
| Four shared runner policy cases | Invoke existing single-shard Python `run`/`verify`. Use the existing Windows Aseprite fixture for ordinary exit 13. | Original Bash/uv wrapper and POSIX SIGTERM producer. |
| Four Linux runtime provisioning cases | Explicit shell scope; no Windows pass. | POSIX executable/path, display, probe, output and cleanup assertions. |
| 37 hosted workflow cases | Explicit shell scope; no Windows pass. | PR resolve/parents/recheck, job gates and configuration output. |
| Three aggregate action cases | Explicit shell scope; no Windows pass. | Bash `pipefail`, `tee`, matrix parsing and summary-file effects. |
| 15 publication cases | Explicit shell scope; no Windows pass. | Guards, upload workspace, controlled upload/edit and retry effects. |
| 11 release maintenance cases | Explicit shell scope before Bash discovery or launcher symlinks; no Windows pass. | Real Git operations, remote SHA, convergence, latest CI and summary. |

The resulting classification is **six Windows shared observations and 70 Linux
workflow observations**. Five of the six were raw failures; the sixth was the
invalid raw pass. All 26 historical mixed-shell passes belong to the shell scope
above. No historical raw counts are rewritten.

## Shared coverage and limits

Existing native runner tests continue to exercise partitioning, original IDs,
worker counts, matrix defaults/overrides, real Git source identity, incomplete or
contradictory reports, and all-skipped refusal. Two direct CLI cases additionally
check that `run` and `verify` reject a target SHA that differs from current HEAD
before creating output. These tests do not verify PR API state or merge parents.

Native archive/PyPI and metadata tests retain the portable release-file rules.
They do not prove the publication job's attestation workspace or GitHub retry
composition on Windows. Likewise, direct report validation does not prove
`pipefail`, `tee` or `GITHUB_STEP_SUMMARY` effects. The JSON mapping labels these
as shared subsets only.

Applicable-host negative witnesses now retain their intended reason: host probe
invocation receipts, a working control for silent job gates, the existing invalid
configuration error, and the existing PyPI refusal message. Admission records
actual arguments and its controlled failure marker. A shell startup failure or
missing fake cannot satisfy these observations.

## Boundaries

No workflow or product code is migrated. The trusted admission remains inline
without checkout, as required by [ADR-0098](../adr/0098-release-only-private-native-runner.md).
Working POSIX paths remain. Windows uses native PowerShell and Python; no Bash/WSL
fallback, universal launcher, Windows CI or persistent host change is introduced.

Windows scope exclusions are reported as skips, never repaired capabilities.
Linux execution evidence comes from the existing Linux checks at the exact
candidate head. Neither those checks nor controlled API tests prove live GitHub
scheduling, runner-group enforcement or real publication.

Per-run results and hashes belong to the PR and issue receipts. The mapping is a
review artifact, not a runtime registry or a requirement to maintain another test
framework. #234 retains final integrated acceptance; unrelated #223/#231 and real
#232 prerequisites keep their existing owners.
