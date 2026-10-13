# Issue #226: literal CLI JSON and discovery evidence

[#226](https://github.com/aigengame/aseprite-automation/issues/226) preserves
literal JSON received by SPA and the existing executable-discovery evidence.
The development baseline is milestone integration commit
`5448b37d6e937321980f90ff1e46013f3833e2e6`; the implementation is `c7eab36`.

The CLI uses the framework's existing `windows_expand_args=False` option when
entering the command. This prevents environment-variable, home-directory and
wildcard preprocessing of the whole argv before validation. The locked versions
are Typer 0.27.2 and Click 8.5.0. Click's official
[expansion guidance](https://click.palletsprojects.com/en/stable/faqs/#shell-variable-expansion-on-windows)
documents this option; the installed Typer command forwards it.

Runtime discovery still applies its own `Path.expanduser` and preserves original
`requested_path` and `searched` evidence. There is no runtime, Application, Core,
Lua, schema, dependency or packaging change. No variable-template or path
compatibility mechanism is introduced.

## Native Windows verification — 2026-10-13

The host uses PowerShell 7.6.5 and CPython 3.13.7 with CP936, redirected GBK
stdio and UTF-8 mode 0. Neither `PYTHONUTF8` nor `PYTHONIOENCODING` is set.
SPA retains the source-owned UTF-8 entry policy delivered in #235. No Bash,
Git Bash, WSL or encoding environment workaround is used.

Before the repair, the percent-delimited JSON field is replaced with the
child-scoped environment value in all three real entries: project console,
supported `main()` call and the previous ordinary wheel. The existing unknown-user
argv discovery test also loses its literal input, while its environment control
passes: **4 failed / 1 passed**. The minimal repair changes the project-entry and
original-discovery subset to **4 passed**; the old wheel is not reused as a
repaired candidate.

The regression then covers both `%SPA_TEST_LITERAL_VALUE%` and
`$SPA_TEST_LITERAL_VALUE`. Each of the three real entries receives identical
JSON through argv and stdin. Strict UTF-8 captures preserve the original field,
`extra_forbidden`, exit 2 and empty stderr; the two complete Failure Envelopes
are equal and validated against that entry's own installed schema.
All **six new regressions pass**. Together with both unchanged discovery
variants, the final targeted replay reports **8 passed**.

The complete CLI, MCP-process and runtime integration families report
**57 passed / 21 failed / 7 skipped**. Their breakdown is:

| Family | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| CLI commands | 40 | 0 | 1 |
| MCP process | 8 | 0 | 2 |
| Runtime integration | 9 | 21 | 4 |

The runtime failures retain invalid POSIX producers and belong to #227.
The existing skips remain separately scoped; they are not Windows passes.
After schema readback was made specific to each tested entry, the targeted
eight-test replay passed again.

A separate candidate-wheel discovery control supplies a copied real Python
executable beneath a child-scoped home directory, with no Aseprite resources.
Both argv and environment selection expand `~/python.exe`, find that file and
report the registered `resource_incomplete` with its canonical path. This
observes discovery only; no native Operation is invoked. The exploration's initial
expected error-name spelling was corrected against the existing failure mapping;
product behavior was unchanged.

The candidate uses ordinary `uv tool install` with locked runtime dependencies
in a private tool directory. Wheel consumers run outside the checkout. The
existing installed verifier passes all **145 Kernel resources**. Wheel SHA-256:
`0e9f1256aaaf2ba9c4d46fa70e369ba7dffd0bc7bb6c0ca6b57d0f56294262aa`.
Ruff lint/format checks pass and Pyright with the project interpreter reports
zero errors and warnings.

## Complete non-slow checkpoint

The checkpoint at `c7eab36` reports **4,470 nodes: 1,847 passed / 1,432 failed /
1,140 setup errors / 51 skipped / 0 warnings**, in 330.27 seconds (driver
331.008 seconds). There are no missing, duplicate or unmatched results.

All 4,464 nodes from the delivered #235 checkpoint are retained, including all
4,434 original non-slow identities. All six new literal-field regressions pass.
Exactly one previous outcome changes: the existing unknown-user argv discovery
test changes from failed to passed. Every other outcome classification remains
unchanged. This produces seven additional passes without changing old assertions.

The 63 shell launch refusals remain failures; no Bash/WSL process is supplied or
started. The audit-only project-venv launch guard is removed after the run. It
does not cover every OS process or certify isolated descendants. The owner
excludes slow; original all-tests evidence remains separate. JUnit SHA-256:
`3666af788a86dfb88e831737d90f76419420cba31726b00072db832f31443a48`.

Raw red/green and installed/family XML, strict discovery captures, candidate
distribution, full checkpoint and identity analysis are retained under
`.runtime/issue-226/`. This correction does not establish native Aseprite,
full MCP wire/cancellation or windowed Windows acceptance; those existing
contracts retain their separate issue owners.
