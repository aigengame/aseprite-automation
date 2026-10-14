# Windows fixtures for existing execution boundaries (#227)

## Scope and implementation

This replacement starts from milestone #9 integration commit
`2063272b8caa1fca4cb1c3401db9ac9b2b38bb6e` (PR #245). PR #242 was closed
without merge. Its experiments and counts remain historical evidence.

The issue requires executable fixtures where an existing test selects a program
by path. `tests/windows_executable.py` supplies this Windows-only entry using
distlib's documented `ScriptMaker.make` API. distlib is a locked Windows-only
test dependency. It is not a runtime or build dependency of SPA. Generation copies
the existing native launcher and embeds the fixture script; it does not compile,
build a wheel, install a package, create a virtual environment, or use a shell per
fixture. See the [distlib scripts API](https://distlib.readthedocs.io/en/stable/tutorial.html#using-the-scripts-api).

The private helper accepts the Python body owned by each affected test. Only
Windows branches use it. Existing POSIX shell bodies, Python caller drivers,
signals, and macOS resource/alias assertions remain. The existing semantic helpers
`fake_probe_response` and `script_runtime` select this entry on Windows and retain
their POSIX implementations. There is no all-platform launcher factory.

| Existing boundary | Treatment |
| --- | --- |
| CLI request/environment selection, Runtime probe, Plan, transport, Script, and installed manifest | Keep the external CLI calls and assertions; adapt the controlled selected executable on Windows. |
| Direct adapter resource/response observations | Keep direct adapter calls; do not add an outer CLI. |
| Direct native fixture diagnostics | Keep real subprocess execution, ordinary exit status, and both captured streams. POSIX signal evidence stays POSIX. |
| Resource-absent, deliberately invalid program, ignored environment, preparation refusal | Keep original files and failure/no-invocation conditions; no unused native entry. |
| Script file-source refusal | Keep the valid probe and the caller body that must not run: the existing flow probes before validating that file. An invalid program cannot witness this refusal. |
| Pure process timing/cleanup module tests | Remain owned by #230. They need no new executable-path abstraction. |
| Installation delivery | Remains separate from the ordinary installed test CLI. |

The controlled Windows script owns UTF-8 and LF for its text output. Byte writes
and request/echo copies stay byte-preserving. The nested diagnostic pytest process
explicitly writes UTF-8, and its consumer and XML reader explicitly read UTF-8.
No suite-wide encoding environment override is used. No product or Lua code is
changed.

## Producer evidence

The existing direct-fixture success test first failed with WinError 193. With the
Windows entry, the same call and assertion passed. The initial default temporary
directory access error was a separate test-environment failure; the red/green
runs used their own temporary roots.

At implementation commit `7e309fdd198340b7e48e1d4175b7eb6e22dea2b1`:

- Direct witnesses: **6 passed, 1 skipped**, in 2.96 seconds. The one skip is the
  retained POSIX signal parameter. These cover ordinary status 0/13, literal
  arguments (including empty and quoted values), stdout/stderr bytes, file effects,
  UTF-8 response bytes, exact probe echo copying, and separate probe/caller behavior.
- A separate local replay directly launched **43 generated producers** in 30.271
  seconds, including intentional sleeps. It checked ordinary exits without Python
  tracebacks, Plan response copying, recorded argument lines, invocation counting,
  and the executable/resource observation. These are producer observations, not
  43 passing SPA integration tests. Replay used bodies from the first family run
  with the current Windows entry; it is not a second execution of those test nodes.
- Static comparison confirms **31 existing POSIX `fake_aseprite` calls across six
  files** retain their original AST, including all body literals. This is not
  macOS/Linux runtime evidence.
- Directly evaluating and launching the two existing Windows bound producers
  confirmed a silent 3.410-second wait and exactly 70,000 output bytes (0.328
  seconds), both with status 0. This verifies their inputs for #230, not SPA's
  deadline or output-bound enforcement.

## Declared-file node mapping

Both old nodes called `os.mkfifo` unconditionally. Each is now split into ordinary
and Unix-FIFO parameters. No Windows FIFO or named-pipe support is added.

All names below are in `tests/script/test_integration_run.py`, with prefix
`test_declared_file_observations_follow_only_successful_execution`.

| Old parameter | New parameters | Retained observations |
| --- | --- | --- |
| `[0]` | `[ordinary-0]`, `[unix-fifo-0]` | Actual write; regular file size; real and dangling symlinks; directory; unavailable child. The Unix parameter also retains real FIFO kind `other`, null size/error. |
| `[7]` | `[ordinary-7]`, `[unix-fifo-7]` | Actual write, process failure, no `files` projection. The Unix parameter retains a real FIFO among declared files. |

Ordinary parameters apply on all platforms. Unix-FIFO parameters apply on
macOS/Linux. On Windows, only an actual WinError 1314 while creating the retained
symlinks becomes a case-local prerequisite skip through #232's existing helper.
These skips do not establish file-observation acceptance.

## Complete non-slow checkpoint

Native PowerShell 7.6.5, CPython 3.13.7 (`win32` / `nt`, UTF-8 mode 0), and
Windows Aseprite v1.3.18.5 ran implementation commit
`7e309fdd198340b7e48e1d4175b7eb6e22dea2b1`. Four workers collected identical
inventories; every selected node has exactly one JUnit outcome. Both slow tests
were deselected. The run completed in 356.19 seconds with exit status 1 and no
warnings.

| Selection | Passed | Failed | Setup error | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,140 | 0 | 0 | 52 | 1,192 |
| Integration | 680 | 133 | 0 | 84 | 897 |
| E2E | 52 | 1,278 | 1,049 | 8 | 2,387 |
| Complete non-slow | **1,872** | **1,411** | **1,049** | **144** | **4,476** |
| Affected complete families (subset) | 156 | 55 | 0 | 13 | 224 |

Affected families are all of `tests/runtime` and `tests/script`, plus
`tests/plan/test_integration_plan.py`, `tests/sprite/test_integration_transport.py`,
`tests/paint/test_integration_native_paint_candidates.py`, and
`tests/cli/test_integration_commands.py`. This includes their prior passing cases.

Compared with the earlier #232 ordinary checkpoint at `68eb2da` (4,470 nodes),
4,468 literal IDs remain. The two declared-file IDs map to the four parameters
above; four Windows-only producer nodes are new. No other original node is removed.
The two original declared-file skips remain in the historical report; all four
replacement parameters skip here (two actual symlink-permission skips, two Unix
FIFO skips). No elevated execution was performed.

Transitions among retained IDs:

- 18 previously skipped request/refusal checks now pass.
- Two direct native diagnostic failures now pass with valid Windows producers.
- Eight previously skipped execution checks now fail; their functional assertions
  remain visible and pending.
- One former pass now fails: `test_probe_failure_evidence_reaches_pytest_reports[expected]`
  previously caught the `RuntimeIssue` caused by an invalid executable. A valid
  producer reaches the unhandled WinError 10038 capture defect. It must not be
  reported as a fixture regression repaired by restoring the invalid executable.

The full JUnit contains 2,198 nodes with WinError 10038 text and 63 refused shell
requests; these are overlapping observations, not independent defect counts or
predicted future passes. In the affected families, 17 of the 55 failures directly
retain WinError 10038 evidence. Other failures often stop at empty-stdout JSON
decoding or outer assertions; their individual root causes are not proved by those
outer traces. #230 must rerun them and retain newly reached failures.

The audit used the same explicitly supplied ICC and isolated wheel consumer as
#232. The reused wheel hash is
`0e9f1256aaaf2ba9c4d46fa70e369ba7dffd0bc7bb6c0ca6b57d0f56294262aa`;
it is not a newly built candidate-wheel acceptance result. The real wheel `info`
test still exposes WinError 10038. Test-only dependencies do not enter SPA runtime
requirements. Final installation/native effects remain #234 acceptance.

Raw logs, inventories, all-node outcomes, exact transitions, launch traces and
producer receipts remain locally under `.runtime/issue-227-replacement/`. The
complete JUnit SHA-256 is
`a27056a6b12559696d0dff190fc88d56a3b857181c7e939f2b430fe73e9b0a91`.
After the run, both temporary audit registrations were absent and the bounded
process query found no Aseprite process. Earlier runs are not overwritten or
combined with this checkpoint.

## Remaining boundaries

Valid producers do not fix SPA's Windows pipe capture. #230 owns remaining
WinError 10038 and capture/timeout/cleanup acceptance. #232 owns real-symlink
prerequisite evidence; #234 owns final integrated acceptance. No test assertion is
weakened to turn these failures or missing prerequisites into passes.

Local commands use native PowerShell and Windows Python/Aseprite with direct
subprocess arguments. The full audit rejects Bash/WSL requests at the instrumented
Python launch sites before creation. That hook is not an OS-wide process security
boundary. No slow tests, Windows CI, UAC, persistent host changes, or Core changes
are part of this increment. Hostnames and absolute local paths are omitted here.
