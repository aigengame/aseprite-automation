# Issue #235: source-owned UTF-8 process entries

[#235](https://github.com/aigengame/aseprite-automation/issues/235) corrects the CLI
and optional MCP process entries and the affected SPA-owned test reader. Native
Windows callers can send UTF-8 JSON and receive the existing Unicode field
locations, typed failures and early usage errors without encoding environment
workarounds.

The implementation adds one standard-library entry helper and calls it from
both `main()` roots before parsing or emission. It retains each stream's error
policy. Importing either module does not change global streams; the MCP entry
does not import CLI/Application internals for configuration. The shared real
SPA test helper and seven further evidenced SPA-output readers explicitly send
and read UTF-8. Core, Application, Kernel
semantics, packaging metadata and external native diagnostic decoders are unchanged.

## Native Windows validation — 2026-10-13

The entry implementation was measured at `5e2f8a7555d5ab65d8870e4e24cc24f2024c2972`;
the final reader correction is commit `c93e924`,
from native PowerShell 7.6.5 with CPython 3.13.7 on Windows 11 x64. The host locale
is CP936, Python UTF-8 mode is 0, and `PYTHONUTF8`/`PYTHONIOENCODING` are absent.
Existing `main()` child probes use `-X utf8=0`; no suite-wide encoding switch,
`chcp`, Bash or WSL is used.

| TDD slice | Before its repair | After its repair |
| --- | --- | --- |
| Real CLI raw UTF-8 `中文` / `中文🚀` stdin | Both lose the field location and produce an unrelated rejection | Both preserve the original extra-field location and `extra_forbidden` |
| MCP early Unicode usage error | Original argument is not preserved in UTF-8 stderr | Original argument is preserved; exit 2 and empty stdout remain |
| Existing SPA helper reads the real Unicode failure | GBK reader fails on producer UTF-8 output | Strict UTF-8 readback preserves the original field and failure |

An initial sample was insufficient: its bytes could round-trip through GBK and
appear correct at the final reader. The retained regression uses the actual
previously failing audit inputs above, plus escaped stdin, argv and early errors.
Raw producer assertions remain independent of the corrected text helper.

The complete affected CLI/MCP process modules report **42 passed / 3 skipped**.
These include real project console, supported `main()` and isolated candidate
wheel entries, MCP early stderr, actual `Cli`-to-SPA child calls, normal helper
readback, import side effects and existing ASCII contracts. The three unchanged
skips are one POSIX fixture (#227) and two cancellation observations (#233).
They are not Windows capability passes.

The candidate wheel is installed through ordinary `uv tool install` with locked
runtime dependencies and the MCP extra. Its consumers run outside the checkout.
Wheel SHA-256:
`3526719adeac10ab593eae71b03a85e1e2ee0e4e75474c62dec4ff60b7fbe75b`.
The existing installed-resource verifier passes all **145 Kernel resources**.
Ruff lint/format checks pass; Pyright with the project Python reports zero errors
and warnings. An initial Pyright invocation selected the global Python and could
not resolve installed dependencies; selecting the project interpreter resolves it.

## Complete non-slow Windows checkpoint

The final candidate (`c93e924b66216231983827785114263182865ed9`) reports
**1,840 passed / 1,433 failed / 1,140 setup errors / 51 skipped / 0 warnings**
from **4,464 selected nodes**, in 338.48 seconds (driver 339.474 seconds).
All 4,434 original non-slow identities retain their outcome classification;
all 30 added entry regressions pass. There are no missing or duplicate results.
Two original slow nodes are explicitly excluded, not counted as skips or passes.

The 63 refused shell launches remain visible failures. The 2,185 traces containing
WinError 10038 and 1,140 setup errors remain unrelated runtime/fixture/prerequisite
work; this checkpoint is not whole-Windows acceptance. Raw symptom groups overlap
and are not independent defect counts. JUnit SHA-256:
`fb599450e82a265a97056df426f686e296a93b37b2f2c11be7d007c43dd38db8`.

The first non-slow checkpoint had 70 GBK reader-thread warnings across eight
test files. The producing processes enter SPA or invoke its installed console.
Five test readers and two example readers now specify `encoding="utf-8"`, with
no change to their assertions or to direct Aseprite decoders. Replaying the
70 original warning nodes removes all reader warnings; their existing native
failures remain visible. This is implementation feedback from reached output,
not a speculative whole-repository encoding rewrite.

The owner excluded slow tests during this implementation. The earlier attempt
that selected slow was stopped along with its owned processes, and is not used
for acceptance totals. The original 2026-10-12 all-tests baseline remains intact.
An audit-only project-venv launch guard refuses Bash/WSL before process creation;
it neither supplies alternate tools nor represents an OS-wide process boundary.
The guard is removed after the checkpoint.

Raw TDD XML, focused XML, candidate distribution, launch metadata, full checkpoint
XML/logs and identity reconciliation are retained locally under
`.runtime/issue-235/`. This evidence is an entry correction, not complete Windows
runtime, full MCP wire or windowed capability acceptance. Those gates retain their
existing issue owners. No Unicode-path workstream, code-page fallback framework,
separate Windows installer, Windows CI or broad Core change is introduced.

## Unix validation

Windows observations do not establish Unix parity. Existing Linux CI checks
against the PR candidate are recorded separately; no Windows CI is added.
