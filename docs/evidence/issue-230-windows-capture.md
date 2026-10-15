# Bounded Windows native capture (#230)

## Change boundary

The branch starts from milestone #9 integration commit
`108808496009a60d67ae0834490cfa1a7af36f5b` (merged PR #248).
The existing Runtime Integration `_run` entry still owns process launch,
the invocation deadline, per-stream byte limits, UTF-8 replacement decoding,
status and registered timeout/overflow evidence.

Windows uses the private `windows_capture.capture` function. Python supports
nonblocking Windows pipes through `os.set_blocking` since 3.12; SPA already
requires Python 3.13 or later. See [Python's pipe support](https://docs.python.org/3.13/library/os.html#os.set_blocking).
A real CPython 3.13.7 probe confirmed not-ready reads, bytes and EOF. The reader
polls both pipes, takes at most 8,192 bytes per read and retains at most 65,536
bytes per stream. An idle poll waits at most 10 ms, bounded by the existing
deadline. EOF returns to the common wait using the remaining original deadline.
No reader threads, queues, unbounded `communicate`, process framework or new
runtime dependency is introduced. POSIX retains its selector path.

The capture setup and read loop are inside the existing process cleanup boundary.
An unexpected error kills a still-live owned child, waits for it and closes both
pipes before unwinding the invocation workspace. The original error propagates;
there is no generic retry or suppression of a live-child cleanup error.

Only Runtime Integration production Python changes. Core, Application, packaged
Lua Operation semantics, public schemas and packaging configuration do not change.

## Incremental verification

- The first real Python child test reproduced WinError 10038, then passed with
  status 13 and exact stdout/stderr including UTF-8 and CRLF.
- The initial module/diagnostic group passed **13 tests**, with **1 retained POSIX
  signal skip**, in 7.15 seconds. It exercised byte limits, overflow, timeout and
  cleanup. Review later found that its Windows venv child did not establish early
  EOF; the corrected real-child evidence is recorded below. Its POSIX witness stays.
- A newly reached Windows diagnostic assertion used `exit status 13`, while the
  existing process failure says `exited with status 13`. The assertion now checks
  that actual positive-exit message and still requires the status and both streams.

At code commit `68d6892df84de8ced03cd4ceb1d80678b0f1a995`, the complete focused
selection ran **237 nodes = 221 passed / 4 failed / 0 errors / 12 skipped**.
All four failures were exact Script stdout expectations. Independent direct
Aseprite capture proved Windows text stdout expands LF to CRLF, including a
second CR after an explicitly emitted CR. The byte receipt was
`63616c6c6572206f75747075740d0a00ff807261770d0d0a`.
SPA retains these native bytes and applies the existing UTF-8 replacement policy;
it does not normalize newlines. Four exact test expectations now use the native
line ending. The complete Script E2E file then passed **8 tests** in 21.89 seconds.
The follow-up is test-only commit `2cd63a1c5f5402682446ed0cbfb8800e572c05c9`.

The focused selection includes complete Runtime, Script, Plan integration,
Sprite transport, candidate Paint and CLI families, plus the existing real
create/paint/PNG-export/wheel-export and both real MCP E2E witnesses. All listed
real runtime, creation, paint, verified PNG, current MCP and legacy MCP witnesses
passed; their original persistence, pixel, schema and file-effect checks remain.
The four Script failures and later passing run remain separate receipts.

## Fresh wheel and windowed preparation

The implementation wheel was installed through `uv tool install` into an owned
isolated tool directory, with the existing locked dependency versions and MCP
extra. The original installed-CLI verifier passed version and all **145 Kernel
resource hashes** outside checkout imports. Existing wheel `info` and verified
PNG export E2E tests also passed through that consumer. The ordinary developer
installation was not replaced. The final gate still belongs to #234.

The unchanged seven-case `tests.filter.windowed prepare` command succeeded at
`68d6892` and produced the seven-case manifest and native files. This is preparation
evidence only. No editor/dialog interaction or reopened GUI-output comparison was
performed; those remain #234's operator-assisted acceptance.

## Limited real-alias witness

The owner approved one additional temporary UAC validation process, limited to
the five existing alias nodes explicitly listed in #230 plus real file/directory
symlink probes. It pinned test revision `2cd63a1`. Both probes succeeded and all
**5 nodes passed / 0 failed / 0 errors / 0 skipped**, in 15.27 seconds.

JUnit SHA-256:
`1882b431bcb412f9932543b5b5274cfbbc303d267c81e5c65de92c8fdcff2e19`.

This retains the Animation destination refusal, Paint in-place publication,
canonical executable/resource observation, and both absolute-symlink Selection
Artifact refusal checks. These five passes are not added to ordinary-token totals.
The earlier #232 121-node witness remains separate historical evidence.

The temporary process exited; its bounded process query found zero matching
Aseprite survivors. A subsequent ordinary process remained non-admin and both
symlink probes still returned WinError 1314. Developer Mode remained unconfigured.
No Developer Mode, registry, privilege policy, whole-suite elevation or persistent
host change occurred. This authorization is finished and permits no further UAC run.

## Complete non-slow audit

At code/test commit `2cd63a1c5f5402682446ed0cbfb8800e572c05c9`, four workers
collected identical inventories. Every selected node has exactly one JUnit result:
**4,483 = 4,213 passed / 127 failed / 0 setup errors / 143 skipped**.
Two slow nodes were deselected. Pytest took 2,993.99 seconds; the audit and
reconciliation took 2,994.65 seconds. Exit status was 1. No warning was reported.

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,140 | 0 | 0 | 52 | 1,192 |
| Integration | 731 | 90 | 0 | 83 | 904 |
| E2E | 2,342 | 37 | 0 | 8 | 2,387 |
| Total | 4,213 | 127 | 0 | 143 | 4,483 |

JUnit SHA-256:
`e7f377b83e551ef012677e7c22f590616d85605a7592fdcdf4bb36374f2ec035`.
Wheel SHA-256:
`cb2ea47fa0c972c959b84b7a05d6d7fea40def3d28cae85f3e778ecc1a402fa6`.

All 4,476 nodes from #227's `7e309fd` checkpoint are retained, with seven new
Windows module witnesses. All 1,872 previous passes remain passes. Among those
same original nodes, 1,311 previous failures and 1,022 setup errors now pass;
27 former setup errors reach later failures. One former skip executes. These
are measured transitions, not a claim that one capture repair solves every test.
The earlier checkpoint and its counts remain unchanged.

The [exact node data](issue-230-windows-checkpoint.json) records all 270
nonpassing nodes with their first demonstrated boundary and owner, and the
unchanged identities of all 168 historical JSON readers plus real legacy MCP.
The JSON readers are **167 passed / 1 failed**; legacy MCP passed. The sole
remaining reader failure is Selection's `explicit_canvas[tilde]`: export succeeds,
then test-side home-relative construction crosses volumes and raises before
the later calls. It belongs to #243. None of the 169 identities is dropped or skipped.

| Remaining owner | Failed | Skipped | Demonstrated boundary |
| --- | ---: | ---: | --- |
| [#223](https://github.com/aigengame/aseprite-automation/issues/223) | 8 | 0 | README UTF-8/newline fixtures and readback. |
| [#224](https://github.com/aigengame/aseprite-automation/issues/224) | 0 | 12 | Tilemap pre-native refusal fixtures. Its 18 Script nodes now pass. |
| [#225](https://github.com/aigengame/aseprite-automation/issues/225) | 6 | 0 | WinError 206 before SPA: Animation's 1,025 observations and five Tile reorder variants. |
| [#228](https://github.com/aigengame/aseprite-automation/issues/228) | 5 | 0 | Existing controlled-CLI MCP stdio fixtures; separate from passing installed MCP. |
| [#229](https://github.com/aigengame/aseprite-automation/issues/229) | 75 | 0 | Existing workflow shell/tool fixtures and admission. |
| [#231](https://github.com/aigengame/aseprite-automation/issues/231) | 2 | 0 | Sibling cleanup observation timeout and localized reused-output assertion. |
| [#232](https://github.com/aigengame/aseprite-automation/issues/232) | 8 | 122 | Actual WinError 1314 before real symlink observations. |
| [#233](https://github.com/aigengame/aseprite-automation/issues/233) | 0 | 2 | Windows cancellation observation not yet adapted. |
| [#243](https://github.com/aigengame/aseprite-automation/issues/243) | 3 | 0 | Home-relative Selection construction across different volumes. |
| [#254](https://github.com/aigengame/aseprite-automation/issues/254) | 20 | 0 | Existing absolute Dithering Matrix inputs incorrectly joined to the working directory. |
| Retained OS-specific witnesses | 0 | 7 | Three macOS launch/sandbox, two POSIX signal and two Unix FIFO cases. |
| Total | 127 | 143 | No unowned nonpass remains. |

The eight #232 failures occur inside test bodies at newly reached symlink
creation sites: seven alias cases and one resource-fork fixture. They are
reported failures, not pytest setup errors or proven SPA functional defects.
Their actual permission failure needs local fixture handling and later valid
execution evidence. The five separately approved alias passes above are not
added to these ordinary-token totals.

#254 has 19 CLI failure receipts with `dithering_matrix_invalid / missing` and
one direct-native state witness. A separate native probe confirms that the
original installed Matrix file exists and `app.fs.isFile` accepts either
separator spelling. The resolver tests only a leading `/`, joins the drive-
absolute path to the working directory, then sees a missing file. A private
copy of the state witness exposes the same rejection while preserving Source
bytes. Its original assertion remains. This establishes the next boundary;
no Color Mode, Export or path framework repair enters #230.

The audit uses native PowerShell 7.6.5, Windows CPython 3.13.7 (`win32` / `nt`,
UTF-8 mode 0), Windows Aseprite v1.3.18.5, the fresh wheel consumer and the admitted
caller-supplied Apple ICC. A temporary Python audit hook refuses Bash/WSL requests
at instrumented launch sites; it provides no alternate shell and is not an
OS-wide process security boundary. Local audit-only return receipts retain failing
CLI status/stdout/stderr before test-side JSON reading can hide the first failure.
No suite-wide encoding override or Windows CI is added. Both slow tests are excluded.
Both temporary audit registrations were removed after the run. The bounded
native-process query found no Aseprite process. The complete JUnit has zero
WinError 10038 occurrences.

## Independent review and corrected EOF evidence

Two independent `gpt-6.1-sol` high-effort reviews assessed Standards and Spec at
`18666b5`. Neither found a production defect or scope expansion. The review's
test concern was adopted: the Windows EOF witness depended on startup speed,
and a venv redirector retained the pipe writers even after the Python child
closed its descriptors. Its checkpoint pass did not prove early EOF.

Independent probes compared the same standard-library child under base Python
and a venv redirector. Only direct base Python produced both EOFs while the
child stayed alive. No extra handle-closing operation was needed. The Windows
tests now launch that owned interpreter directly. The EOF child writes both
streams, closes them, then waits on its explicit stdin pipe. The module clock
advances from 0 to 0.75 only after real capture reports both EOFs. The test
observes an actual 0.25-second wait from the original one-second budget, then
real timeout, kill and wait. A wall-clock guard bounds a broken witness.
The POSIX body is unchanged; no launcher or common platform fixture is added.

This test correction is committed as `8621cb9f118d02d9fff56baf41b4f71fd1b2934e`.
The formal guard/diagnostic rerun passed **13 tests**, with **1 POSIX signal
skip**, in 6.02 seconds. A private mutation that resets the wait to the full
one-second budget is rejected by the corrected witness. Independent re-review
accepted the correction. Production source and the wheel are unchanged.
This is separate follow-up verification, not a second full-suite run or a rewrite
of the `2cd63a1` statistics.

Raw reports, inventories, launch/CLI receipts, producer probes, windowed preparation
and the separate UAC witness remain under `.runtime/issue-230/`. Host identifiers
and absolute local paths are omitted from this public report.
