# Issue #227: native controlled runtime fixtures

[#227](https://github.com/aigengame/aseprite-automation/issues/227) repairs invalid
controlled producers and diagnostic readers. It does not repair SPA's native
capture path. The integration baseline is
`08711223425709bbe5357164707c5d5c2b3f8fc6`; the tested implementation is
`fcb256316310fc6ebeec399f7dac686cf4389d52`.

## Fixture change

`tests/console_program.py` builds and installs a small stdlib-only Python console
program with the existing uv toolchain and the repository's pinned build backend.
The build is offline after the normal environment sync. Each producer retains its
own Python body, actual console launcher and Aseprite bundle/resource layout.
There is no production code, public CLI option, dependency, package contract or
process-supervisor change.

The producer entry owns UTF-8 and LF text streams. It also retains the executable
name in `argv[0]`: the installed uv launcher strips `.exe` on Windows, while the
existing launch-identity assertion requires the actual executable path. No other
argument is rewritten. Requests and echoes are copied as bytes; response files
use explicit UTF-8. Caller script bytes and ordinary file effects remain intact.

The runtime, Plan and Sprite transport producers now execute Python bodies rather
than POSIX shell text. The script producer handles both the existing probe and
caller program without a shell wrapper. Pytest XML is read explicitly as UTF-8.
The smallest signal/FIFO parameters retain their real Unix prerequisites and
assertions; ordinary parameters are selected on every host. Real symlinks are retained.

## Direct producer verification

The original direct exit/output tests reproduce **2 failed / 1 skipped** with
WinError 193, then reach **2 passed / 1 skipped** with valid console launchers.
The signal case remains a real POSIX-signal test on macOS/Linux.

Three additional real-process tests pass before SPA capture is involved:

- Exact request/echo bytes and UTF-8 response bytes, including null, booleans,
  Chinese text and an emoji; the existing `gui.xml` resource identity is retained.
- Exact caller source bytes, including BOM content and CRLF, stdout/stderr,
  ordinary exit 7 and a real `effect.bin` write.
- Actual console executable identity and literal JSON argv containing percent and
  dollar fields despite a matching child environment variable.

The first script-stream check exposes CRLF, and the first launch-identity check
exposes the stripped suffix. Both fail before their local producer-entry repair;
the final producer run is **3 passed**. Together with the two restored direct
tests, there are **five passing direct producer witnesses**. Separately, bounded
direct runs of the generated Plan and handler-argument fixtures verify one LF
counter append, exact recorded arguments and response bytes. All 52 generated
producer modules in the focused run compile. These observations are independent
of SPA's failing capture implementation, not business-capability passes.

## Native Windows checkpoint — 2026-10-13

The host uses Windows 11 x64, PowerShell 7.6.5, CPython 3.13.7, CP936 and redirected
GBK stdio with UTF-8 mode 0. Neither `PYTHONUTF8` nor `PYTHONIOENCODING` is set.
Only the project console directory is prepended to PATH. No Git Bash is injected;
no Bash/WSL fallback is used. The audit-only project-Python hook refuses explicit
shell attempts before creation and is removed after the run. Its 63 refusals are
failed Linux-workflow harness tests under #229, not Windows capability evidence.
The hook is not an OS-wide security boundary.

The owner excluded slow tests. All **4,478 non-slow nodes in 205 files** are
reported exactly once, with no collection errors, missing or unmatched nodes:

| Tier | Passed | Failed | Setup errors | Skipped | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unit | 1,138 | 13 | 40 | 1 | 1,192 |
| Integration | 679 | 145 | 51 | 24 | 899 |
| E2E | 52 | 1,283 | 1,049 | 3 | 2,387 |
| Total | **1,869** | **1,441** | **1,140** | **28** | **4,478** |

Pytest reports no warnings. The run takes 375.109 seconds and exits 1. It reuses
the ordinary uv-tool-installed #226 wheel because `src/`, `pyproject.toml` and
`uv.lock` are identical to that candidate. Its SHA-256 is
`0e9f1256aaaf2ba9c4d46fa70e369ba7dffd0bc7bb6c0ca6b57d0f56294262aa`.
Real Aseprite remains the published v1.3.18.5 build (`1.3.18.5-dev`, Lua 5.4/API41).

The complete affected runtime, script, Sprite transport, native Paint candidate,
Plan integration and CLI families contain **226 nodes: 154 passed / 61 failed /
11 skipped**. All run again in this checkpoint, including existing passes. The
focused precheck has the same classifications, but three nested pytest reports
first encounter an existing default-Temp permission problem. The checkpoint uses
a writable task Temp root: all three now reach WinError 10038, and their UTF-8 XML
reports read successfully. The precheck's Temp errors are not transport evidence.

## Original node conservation and limits

The previous #226 checkpoint has 4,470 nodes. This checkpoint retains 4,465 literal
identities, maps five old nodes to ten explicit parameters, and adds three direct
producer tests: `4,470 - 5 + 10 + 3 = 4,478`. All 4,434 original non-slow identities
from the 2026-10-12 audit are retained literally or through that mapping. Prior
raw statistics are not rewritten. The issue's 46 distinct frozen evidence anchors
map to 50 current nodes: **2 passed / 44 failed / 4 Unix-only skips**.

Exact old and new IDs, retained assertions, host scope and Windows outcomes are
recorded in [issue-227-node-mapping.csv](issue-227-node-mapping.csv). The three
old pytest-report phases each split into `ordinary-exit-*` and `unix-signal-*`;
the Unix cases still require actual SIGTERM and the original negative exit status.
The two declared-file nodes split into `ordinary-0/7` and `unix-fifo-0/7`.
Successful Unix FIFO observations still assert `other`, null size and no error;
nonzero execution still retains its file effect and reports no declared facts.
Ordinary variants retain regular/symlink/dangling/directory/unavailable assertions
but fail at real symlink creation with WinError 1314 on this host (#232). Unix FIFO
scope is not counted as Windows success and Windows FIFO support is not added.

Among literal identities, 18 script request/Plan rejection cases move from skipped
to passed, two direct diagnostics move from failed to passed, and eight generic
process/manifest/launch cases move from skipped to failed. The 18 restored
pre-runtime cases partially satisfy #224; its 12 Tilemap cases remain skipped.
No other literal classification changes.

The old `test_probe_failure_evidence_reaches_pytest_reports[expected]` was a
misleading Windows pass: it caught the invalid producer's typed startup failure.
Its valid ordinary-exit variant now fails on the untyped native capture error;
its original Unix-signal variant is correctly Unix-only. This is recorded as
exposed #230 evidence, not removed coverage. WinError 10038, sometimes followed
by WinError 32 while cleaning a still-used workspace, remains the native transport
blocker. Business, timeout and stream-limit assertions are preserved. The 1,140
setup errors and unrelated failures remain in the full report. This fixture slice
does not claim complete Windows support or windowed Aseprite coverage.

## Retained records

The first Linux CI run at `d7ef0a6` reports **2 failed / 2,074 passed / 15 skipped**.
Both failures are new ordinary-exit report descriptions: the direct fixture helper
says `exit status 13`, while SPA's existing probe diagnostic says
`exited with status 13`. The ordinary report parameter is corrected to assert the
actual SPA description; exit status, both streams, UTF-8 XML and original Unix
signal assertions are retained. A native Windows replay of the complete producer
and diagnostic families reports **5 passed / 3 failed / 4 skipped** across 12
nodes. The three ordinary probe-report cases still fail at #230. This follow-up
does not rewrite the first full checkpoint above; later exact-head validation is
recorded in the PR and task runtime records.

Raw TDD captures, generated producers, direct-effect checks, the current issue
snapshot, full collection/JUnit/console/launch reports, outcome transitions and
the complete prior-node mapping are under `.runtime/issue-227/`. The checkpoint
JUnit SHA-256 is
`45e6ac8010e0b02c21b5de33b4e3e97302b1f6dd8c33da7cb7a15460165cb58d`.
Ruff check, Ruff format (484 files) and project-interpreter Pyright pass.
