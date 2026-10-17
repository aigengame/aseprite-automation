# Final Windows integration observation (#234)

Observed on 2026-10-17 at integration source
`ad07fb4a42b13cf78a572c634e376664cc130f2d`, after PR #266. The tree matches
reviewed source `e9cde4bb5a6177eae70fa29a49f00c48a6675f17`.

## Complete non-slow observation

The ordinary-token run used native PowerShell 7.6.5, CPython 3.13.7
(`win32` / `nt`, UTF-8 mode 0), the locked uv test/MCP dependencies, and
Windows Aseprite `1.3.18.5-dev`. No global Python encoding override was set.
Native calls used direct subprocess arguments. Windows filesystem fixtures
used `powershell.exe`; no Bash, Git Bash or WSL was injected or used as a fallback.

The existing `tests` selection ran with `-m "not slow" -n 8 --dist=load`,
without early failure or worker restart. All eight inventories agree. Each of
the **4,763 selected IDs** has exactly one result; the two existing slow
example rebuilds were deselected. All 4,762 previous IDs remain, with the
delivered #231 Windows interruption regression as the sole addition.

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| unit | 1,279 | 0 | 0 | 72 | 1,351 |
| integration | 773 | 1 | 0 | 139 | 913 |
| e2e | 2,483 | 1 | 0 | 15 | 2,499 |
| **Total** | **4,535** | **2** | **0** | **226** | **4,763** |

Raw exit status is **1**, with **0 warnings** and a wrapper duration
of **2,530.97 seconds**. This is the original complete run, not a total
assembled from focused passes. Earlier checkpoints retain their original
revisions and counts.

### Validation-directory failure

One failure is the unchanged
`tests/ci/test_integration_native_test_policy.py::test_passing_negative_tests_do_not_stop_the_shared_native_step`.
Its nested controlled executable exists, but this observation's deep
`--basetemp` makes its path 262 characters. A direct readback through the
same CLI reports WinError 206 and `process_start_failed`, before the intended
exit-13 / `process_failed` assertion.

A separate run of this same node uses a fresh short owned temporary root:
**1 passed / 0 failed / 0 errors / 0 skipped, 5.30 seconds in the pytest console**. It retains the existing two-worker inner suite and its original
CLI assertions. No test or product source changed. The original full-run
failure remains in the table; this focused result does not turn the raw
command into an all-green run. The validation-root choice does not establish
a new long-path feature or belong to deferred #230.

### Existing Tile reorder timeout

`tests/tile/test_e2e_lifecycle.py::test_reorder_permutations_at_tile_count_limit[reverse]`
reaches its existing 60-second native Operation budget and reports
`process_timeout`. Its retained Target is still `previous target`.
The same unchanged node passes separately with one worker in **42.27 seconds**.
The final limited run of the three original `original/reverse/mixed` parameters
uses eight workers: **3 passed / 0 failed / 0 errors / 0 skipped**,
**48.79 seconds** in the pytest console. The 42.27-second single-node duration
also comes from the pytest console. Both observations retain the original
60-second Operation budget. Further expansion stopped after these observations.

The earlier #225 investigation had already recorded this node's timeout and
a separate pass. Neither result establishes a cause or a repaired Operation.
No timeout, test assertion, product source or performance contract is changed.
This observation is not assigned to #230's deferred cleanup investigation.
**#234 remains open.** The requested full statistics, GUI checks and support
record are complete, but this valid full-run timeout has no established cause
or accepted disposition. Separate successes do not satisfy a claim that the
original full command passed. No new performance mechanism or broader requirement
is proposed.

### Skips and real prerequisites

| Reason | Count | Disposition |
| --- | ---: | --- |
| Actual Windows symlink creation WinError 1314 | 149 | Missing ordinary-token capability; map the separate real witnesses below. |
| Proven hosted Linux workflow shell scope | 70 | Existing Linux-only action/publication composition; no Windows CI requirement. |
| Other genuine OS scope | 7 | Two macOS bundle cases, one macOS agent-sandbox case, two POSIX signals, two Unix FIFOs. |
| **Total** | **226** | **Not functional passes.** |

No skip is counted as a pass. The retained #232 capable-process evidence is
separate: source `bbb181dfb2401fb33158cbb7866b86d97fed0671` ran exactly
149 existing nodes, with **148 passed / 1 failed / 0 errors / 0 skipped**.
That Script assertion was subsequently corrected, and the separately approved
two-node run at `bdd88a6` reports **2 passed / 0 failed / 0 errors / 0 skipped**.
These cohorts overlap and cannot be added to this full-run total.
The 149 current permission-skip IDs match the fixed 149-node capable witness
exactly, with no missing or additional IDs. The later two-node witness includes
the previously failed `ordinary-0` and overlapping `ordinary-7`; the original
149-node receipt is still 148 passes and one failure, not rewritten as 149 passes.

All temporary capable processes exited. The ordinary token still lacks
symlink-creation permission. No persistent Developer Mode, registry or host
permission change is required or claimed. See the
[#232 close-out](https://github.com/aigengame/aseprite-automation/issues/232#issuecomment-6228419105)
and [historical prerequisite observations](issue-232-windows-prerequisites.md).

### Execution audit

Registered project and selected installed-wheel Python launch sites recorded
**23,456 events**, including **18,188 admitted subprocess attempts**,
**zero denials** and **zero forbidden-shell targets**. Consequently no passing
negative test in this recorded scope depends on an audit refusal. Temporary
site registrations were removed. This is launch-site evidence, not OS-wide
process monitoring. A bounded post-run query finds no Aseprite survivor under
this observation's owned roots, no unobservable Aseprite command line and no
remaining audit registration.

## Existing delivery and native data evidence

The existing non-editable `uv tool` wheel consumer was reverified outside
the checkout by `scripts/verify_installed_cli.py`: SPA 0.5.0 and all **145
Kernel resources** pass. The selected wheel was built at `bbb181d`; production,
package metadata and locked dependencies are unchanged through the measured
integration source. No separate Windows installer or new wheel is introduced.

The exact caller-owned 536-byte Apple P3 input was selected explicitly. Its
SHA-256 remains
`0ff6958f98684c61f6bbdce1368ddeaf3873baf84545baba482e920d92a914c0`.
No selected node skips for a missing caller ICC. Existing per-runtime native
conversion gates still apply; supplying the input does not promise conversion
on every runtime.
The ordinary installed CLI, isolated wheel consumer and controlled test
executables remain distinct observations.

## Thirteen real windowed comparisons

All **13 comparisons pass** with the same Windows Aseprite binary. Each real
dialog was inspected and confirmed once with **OK**, without Apply. Thirteen
screenshots and operator observations accompany the UI receipts. All Sources
retain their hashes; saved outputs were closed, reopened and compared with
SPA through the existing native observation helpers. Preparation or a receipt
alone is not counted as GUI evidence.

- **Seven Tilemap Brightness/Contrast cases:** RGB, Grayscale, Indexed, RGB
  Palette colors, linked Cel Images, distinct Cel Images, and spatial Selection
  over offset rectangular Tiles. Brightness 50, Contrast 0, Selected Cels,
  Preview on, Red (or Gray) only, Alpha off, Manual Tileset mode. Reopened
  Images, placement/Tile facts, Palette Changes and resolved colors match SPA.
- **Six Despeckle cases:** RGB Red 3x1; Gray+Alpha 2x1; Indexed Index 3x1;
  Indexed Green 3x1; duplicate-color Index 1x1; duplicate-color RGBA 1x1.
  Preview is on and Tiled is off. Reopened Images, geometry and Palettes match.
  The final pair preserves stored Index 1 for Index processing and remaps it
  to Index 2 for RGBA processing, as in the existing comparison scope.

The editor's temporary Manual mode and Timeline visibility were restored,
the generated document was closed, and the owned window exited normally.
Script-security prompts were handled manually without full trust or alert
suppression. These local GUI observations do not claim automated GUI or Linux CI
coverage. Reproduce with the existing [windowed procedure](../testing.md#local-windowed-tilemap-filter-comparison)
and [Despeckle fixtures](issue-39-native-filters.md#existing-checks).

## Measured platform boundary

The [PR #259 native macOS observation](https://github.com/aigengame/aseprite-automation/pull/259#issuecomment-6188010597)
retains source `4acd2c8`: the complete Selection family is **81 passed /
0 failed / 0 errors / 0 skipped** (67 native E2E and 14 unit), including all
five original tilde variants. Selection test files are unchanged through
`ad07fb4`. The #232 Windows capable witness separately passes all four
absolute/tilde export/preview real-symlink parameters. These are recorded
sources, not new macOS executions at this integration head.

Native Linux Selection was not available for that observation. Routine Linux
CI excludes native Aseprite E2E and cannot supply the missing native result.
The Windows observation establishes the selected runtime and existing test
scope; it does not certify every platform/runtime version. #230 remains
unresolved, deferred and non-blocking. A passing observation is not proof of
an intermittent cleanup fix.

## Retained receipts

Raw JUnit, matching collection inventories, every original-ID outcome, per-file
statistics, launch records, the separate short-root result, and GUI manifests,
Sources/outputs, receipts and screenshots remain in the ignored local
`.runtime/issue-234-final-20261017/` evidence directory. Public prose omits
hostnames, user/security identities and absolute host paths.

| Receipt | SHA-256 |
| --- | --- |
| Complete JUnit | `89c9f4a66d1cc3706f49dbce11c5beeb639de4ef31c4e39aacabc0ebff9d9639` |
| Short-root focused JUnit | `f0d4e937758c5c224329e2c37b5506dd80c86e313590c760035b6f073ffe47dd` |
| Separate reverse-node JUnit | `c3a0b689923c45d881ce1f7d249e7e6ba1dc0880e3189e50feb3f30a5bab43f6` |
| Three-parameter, eight-worker JUnit | `f709f12b2768a09c89c19bd78b2afa1e00efd078491972e9b43ca350a1800945` |
| Seven-case Tilemap comparison | `70e0ad505861a79db1009d01a392e5a6c8790b7c67c098f902ef535b3e67da4b` |
| Six-case Despeckle comparison | `0b93e44449b26b036e5560f25cfd4683e7126c50896a2271ead0d770ed99f552` |
| Existing wheel | `d704f0c3c09802c770eed47580c1188b0778476fb0acfd66ac7e681358fe11bf` |
