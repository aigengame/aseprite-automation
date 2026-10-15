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
- The module/diagnostic group passed **13 tests**, with **1 retained POSIX signal
  skip**, in 7.15 seconds. Real Python children verify both streams at exactly
  65,536 bytes, overflow in either stream, silent timeout, retirement after pipe
  setup/read errors, closed pipes and removable workspaces. The existing EOF
  deadline node now executes on Windows with a real child; its POSIX witness stays.
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

The full ordinary-token run at `2cd63a1` is in progress. Its exact inventory,
outcomes, historical JSON-node mapping and remaining-owner classification will
be recorded when it completes. There is no full-suite success claim at this point.

The audit uses native PowerShell 7.6.5, Windows CPython 3.13.7 (`win32` / `nt`,
UTF-8 mode 0), Windows Aseprite v1.3.18.5, the fresh wheel consumer and the admitted
caller-supplied Apple ICC. A temporary Python audit hook refuses Bash/WSL requests
at instrumented launch sites; it provides no alternate shell and is not an
OS-wide process security boundary. Local audit-only return receipts retain failing
CLI status/stdout/stderr before test-side JSON reading can hide the first failure.
No suite-wide encoding override or Windows CI is added. Both slow tests are excluded.

Raw reports, inventories, launch/CLI receipts, producer probes, windowed preparation
and the separate UAC witness remain under `.runtime/issue-230/`. Host identifiers
and absolute local paths are omitted from this public report.
