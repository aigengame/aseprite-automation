# Test suite

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

## Ownership areas

Each row points to the tests of one behavior owner. The tests and their module
docstrings state what each area covers. This guide does not repeat it. Feature
history and manual native observations are in [`docs/evidence/`](evidence/).

| Directory | Behavior owner |
| --- | --- |
| `tests/animation/` | Animation audit, compare, and preview. |
| `tests/application/` | Application orchestration, including compatibility checks before Operation execution. |
| `tests/cel/` | Cel lifecycle, placement, copy/link relationships, Cel Image size, and document Target facts. |
| `tests/ci/` | README translation freshness, Release admission, native test execution policy, and shard evidence checks. |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/color/` | Color Profile commands and their native stored color facts. |
| `tests/color_mode/` | Conditional Color Mode choices, native mapping/Dithering, complete Sprite and Plan conversion evidence. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration, Operation Descriptor constraints, and the rules that every command shares, as one table for each rule over the command tree, and the checks of `tests/native_invocation.py`. |
| `tests/delivery/` | Shared Artifact staging, verification/publication lifecycles, and real filesystem publication boundaries. |
| `tests/examples/` | Installed-CLI workflows, deterministic asset production, and checked-in downstream asset agreement. |
| `tests/export/` | Image, sprite sheet, GIF, PNG sequence and Tileset Export contracts, independent format verification, and real Aseprite output evidence. |
| `tests/filter/` | Native Filter application, Channels, Cel targets, Palette basis, state restoration, and verified publication. |
| `tests/frame/` | Frame timing, insertion, Cel copy/link intent, Tag adjustment, and native persistence. |
| `tests/image/` | Image crop, canvas resize, orientation, resize, and Snapshots. |
| `tests/import/` | Encoded PNG facts, compatible native Cel insertion, frozen input identity, and publication refusal. |
| `tests/layer/` | Layer hierarchy, exact addressing, and native addition evidence. |
| `tests/mcp/` | MCP protocol projection, CLI process lifecycle, Artifact content, and installed native workflows. |
| `tests/motion/` | Bounded Cel curve sampling, complete preflight, and persisted pixel/property preservation. |
| `tests/paint/` | Paint Domain Module contract, bounded mutation evidence, and native Pixel Patch behavior. |
| `tests/palette/` | Shared Effective Palette resolution over native Frame-based Palette Changes. |
| `tests/plan/` | Static Plan preflight, single-Sprite Step composition, and commit gates. |
| `tests/preparation/` | Frozen input/specification checks, geometry and anchors, native preparation, exact PNG facts, reproduction, and publication gates. |
| `tests/release/` | Release metadata and publication gates. |
| `tests/runtime/` | Aseprite Runtime Integration, including discovery, launch, private Kernel transport, and real-runtime evidence. |
| `tests/script/` | Exact caller-owned Lua transport (`spa script run`), process/file facts, bounds, and exclusion from core identities and Plans. |
| `tests/selection/` | Explicit Selection values and native Selection operations. |
| `tests/slice/` | Complete Slice Keys and coverage, exact addressing, bounded native authoring, exporter validation, and save/reopen evidence. |
| `tests/sprite/` | Sprite Domain Module contracts plus real creation, copy, flatten, bounded validation, persisted reopen, structural inspection, and Target Commit evidence. |
| `tests/tag/` | Tag stored facts, exact current addressing, native mutation, and save/reopen evidence. |
| `tests/tile/` | Tileset/Tile identity and lifecycle, exact Tilemap topology, complete Tile Region transport, native validation, Tilemap Layer create/share persistence, and explicit Tilemap Cel creation. |

Add an ownership directory only when tests for that behavior exist. Keep a helper in
the narrowest ownership directory that uses it. Move a helper to `tests/support.py`
only when more than one ownership area needs it. Each directory is a Python package,
so different owners can safely use the same focused file name later.

### Shared test modules

These modules hold the helpers that more than one ownership area uses. The
docstrings of each module and helper state its contract.

| Module | Holds |
| --- | --- |
| `tests/native_invocation.py` | `run` and `expect_success` for the installed `spa` command, `run_lua` for Lua fixtures, and the `render_frame` render oracle. |
| `tests/conftest.py` | The session `runtime` fixture, the e2e gate, and the native failure report hook. |
| `tests/support.py` | Controlled Aseprite executables, `controlled_runtime`, `observe_cli`, `process_diagnostics`, and the fixture builders that several areas share. |
| `tests/fixtures/observe_cli.py` | The observers that `observe_cli` puts on one SPA adapter seam. |
| `tests/host_permissions.py` | Host-permission fixtures with one call shape on every platform. |
| `tests/native_entry.py` | `python_entry`, which makes a native executable entry from a Python body. |

Use these rules when you write a test:

- Run the `spa` command with `run` or `expect_success`, and a Lua fixture with
  `run_lua`. A test module keeps its own CLI or Lua fixture helper only when the
  helper adds test-specific steps to `run`, `expect_success`, or `run_lua`, and its
  docstring states those steps.
- A fixture builder takes `runtime` as a parameter and does not probe. A test whose
  claim is the probe calls `probe` itself.
- A test that uses a controlled executable uses `controlled_runtime`, not the
  session `runtime` fixture.
- A test of a refusal after the probe and before the Kernel uses
  `probe_only_aseprite`, so the test fails when the request gets to the Kernel.
- Test files do not test `os.name` to select a controlled Aseprite fixture or a
  host-permission step. The shared fixtures have one call shape on every platform.
- A single-consumer fixture stays with its owning tests. It builds on
  `controlled_aseprite` or `deny_access`.

## README translations

The English `README.md` is authoritative. Translations live in
`docs/README.<locale>.md`, beginning with Simplified Chinese (`zh-CN`). Update and
review every translation in the same change as its English source. Preserve the
commands, examples, links and support boundaries; write idiomatically for the
target language. Keep navigation working when translating headings, using explicit
anchors for the English fragment names where needed.

After reviewing the translations, record the current English revision:

```sh
uv run python scripts/update_readme_i18n.py
uv run python scripts/update_readme_i18n.py --check
```

The script discovers `docs/README.*.md` and stamps a leading SHA-256 marker in each
file. Only line endings are normalized before hashing English content. `--check`
does not modify files: a missing or stale marker, or a missing required Chinese
README, fails the check. New locales join the check automatically; add links to
them in the language selectors too.

`tests/ci/test_integration_readme_i18n.py` runs the same check against the repository
in the existing Fast tests job, and verifies failure and refresh behavior with
temporary files. The hash detects an unacknowledged English revision; it cannot
judge translation accuracy or prove that prose was reviewed. Do not refresh markers
as a substitute for reviewing and updating translations. This follows
[godot-agent's README sync workflow](https://github.com/aigengame/godot-agent/blob/94ed02142b989d51d4cc036b6f993b219bea3049/scripts/update_readme_i18n.py).

## Verification tiers

Workflow tests distinguish portable Python rules from hosted Linux shell
composition. Shared admission and runner rules use native Python. Tests that
execute Linux action Bash bodies are scoped off Windows; those skips are not
passes. Native report or archive checks cover their own rules, not pipeline,
publication or GitHub workflow effects.

Use the tier in the file name:

- `test_unit_*.py` exercises rules and contracts in one process.
- `test_integration_*.py` connects SPA components. It can invoke the installed `spa`
  CLI with a controlled fake Aseprite executable, but it does not prove native
  Aseprite behavior.
- `test_e2e_*.py` invokes the installed `spa` CLI with a real Aseprite executable,
  or exercises a shared packaged Kernel Interface directly with native fixtures.
  Mark the module or each test with `pytest.mark.e2e`. A refusal that SPA decides
  before the Kernel call is not an e2e case: test it in the fast tier with a missing
  Aseprite path or a controlled executable.

`pytest.mark.slow` is an additional cost marker, not a verification tier. Use it
for complete example rebuilds, which run locally on demand. Automated CI and
Release exclude these tests. The small wizard probes remain only `e2e`.

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. The selected macOS and Linux execution profiles expose
`_VERSION == "Lua 5.4"` and `app.apiVersion == 41`. The E2E assertion checks the
Baseline Aseprite family while runtime admission uses the Descriptor's observed
language and API requirements. This check does
not certify each later Aseprite release. Do not require an additional version test
solely because another native release exists. An observed defect or newly accepted
requirement warrants a targeted check of the affected Operation.

Pytest rejects unregistered markers. The root e2e gate also rejects a selected e2e
test when `SPA_TEST_ASEPRITE` is absent, is not a file, or is not executable. A missing
runtime therefore cannot produce an all-skipped successful e2e run.

### Local prerequisites

Use the locked `uv run --frozen --group test` environment and its installed `spa`
command. Set `SPA_TEST_ASEPRITE` to the real local runtime. Use a writable temporary
root with room for nested test paths. In the recorded Windows run, a 262-character
controlled-executable path failed with WinError 206; the unchanged test passed
with a shorter root. When the default pytest root is unavailable, select a new
owned directory with `--basetemp`. Pytest can remove a previous directory at that path.

Tests that create real file and directory symlinks need the corresponding
filesystem permission. This is a prerequisite of those observations, not a
configuration requirement for every developer host or ordinary Source test. An
unavailable prerequisite is not a product failure or a pass. Unlistable-directory
and unreadable-file tests retain POSIX permissions on macOS/Linux; their private
Windows fixtures use `powershell.exe` to deny only directory listing or file data
reads and restore the temporary access rules. They do not change host policy.
The caller-supplied ICC identity is described below. The separate wheel consumer
configuration is in [CLI and MCP text entries](#cli-and-mcp-text-entries).
See [#232 Windows observations](evidence/issue-232-windows-prerequisites.md)
for historical prerequisite measurements and the
[Windows integration measurements (#234)](evidence/issue-234-windows-acceptance.md)
for the full-suite/GUI results at `ad07fb4` and the separate packaging check at
`bdaac25`. Neither measurement implies a new full-suite result at a later revision.

Optional caller-supplied Apple P3 checks require `SPA_TEST_APPLE_P3_ICC` to point to
the exact previously admitted local file. They skip when it is unset; tests do not
search the host or download that file. Normal CI needs only the bundled CC0 reference.
See [#194 evidence](evidence/issue-194-redistributable-profile.md).

Tests that read retained example PNGs, such as the wizard tests in `tests/export/`,
need the Git LFS content. Fetch the Git LFS assets first.

### CLI and MCP text entries

The [process text policy](usage.md#process-text-encoding) applies to the CLI and
optional MCP entries. SPA-owned subprocess readers, including `tests.support.spa`,
read and write UTF-8 explicitly.

Select a candidate wheel with `SPA_TEST_INSTALLED_CLI` to include the isolated
installed entries. Set it to the candidate installation's `spa` executable.
Wheel consumers run outside the checkout. Run the entry regression modules
on macOS, Linux and Windows:

```text
uv run --frozen --group test --extra mcp pytest tests/cli/test_integration_commands.py tests/mcp/test_integration_process.py
```

Full MCP wire/native delivery remains a separate runtime-dependent check. Measured
host setup, execution restrictions and results are recorded in
[issue #235 validation](evidence/issue-235-utf8-entries.md).
Literal-input and discovery results are recorded in
[issue #226 validation](evidence/issue-226-literal-cli-input.md).

### Routine verification commands

Run the fast unit and integration tiers with four pytest workers by default:

```sh
uv run --frozen --group test pytest -m "not e2e" \
  -n "${SPA_FAST_TEST_WORKERS:-4}" --dist=load --max-worker-restart=0
```

Set `SPA_FAST_TEST_WORKERS` to change the local worker count; `0` runs serially for
diagnosis. Routine CI uses the same arguments in one job and reads the optional
GitHub repository variable `SPA_FAST_TEST_WORKERS`, with a default of `4`. Each
selected test runs once. Worker crashes fail the run, with automatic worker restart
disabled.

Run the complete routine real-runtime selection, including the small wizard probes,
through the same entry point used by Native E2E and Release:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test python scripts/native_e2e.py run \
  --output-dir /tmp/spa-native-e2e-001
```

Use a new output directory for each run. For complete installed-wheel CLI coverage,
build the current wheel, install it with the locked runtime dependencies in a separate
environment, and set `SPA_TEST_INSTALLED_CLI` to its installed `spa` executable.
Otherwise the existing wheel-only cases report their environment skips.
Routine CI and the Release fast tests do not set `SPA_TEST_INSTALLED_CLI`, so these
cases skip there. The Release quality job adds the `mcp` extra to its wheel smoke
install and runs the `wheel` cases of `tests/cli/test_integration_commands.py`
and `tests/mcp/test_integration_process.py` against it.

The [installed distribution record](evidence/issue-54-installed-distributions.md)
records the tested macOS profile, the isolated-wheel replay, and the remaining
Linux evidence for the Release-only runner. Its earlier Linux build/cache profile
is historical. `scripts/verify_installed_cli.py` rejects editable/source-tree
imports and checks all packaged Kernel resources. Both the distribution smoke action
and the Linux native action reuse that verifier.

To run one ownership area, give its directory. Add `-m "not e2e"` to run only its
fast tiers:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/paint -x -vv --tb=short -rs
```

### Shared native parallel execution

`scripts/native_e2e.py` owns selection, configuration, partitioning, execution, and
report validation for local and Release execution. The shared default is **8 shards**;
worker count comes from each execution host and defaults to **2** when unset.
Local execution starts all shards on one machine; use fewer shards or workers when
that exceeds local capacity. `.github/workflows/native-e2e-shards.yml` submits the
same shards to GitHub's native queue for eligible Linux runners. Each shard uses
xdist's `load` scheduler. Pytest collects the full `e2e and not slow` selection,
sorts the original node IDs, and assigns each ID
by its ordinal modulo the shard count. No file lists or timing database are needed.

The shard count (`--shards N` or `SPA_E2E_SHARDS`) defines the test partition.
Worker count is local execution capacity: `run --workers N` overrides the executing
host's `SPA_E2E_WORKERS`, which otherwise defaults to two. Explicit arguments take
precedence; empty environment values use the shared defaults. Counts must be
positive integers. A runner can execute any shard with its own worker count; neither
the matrix nor aggregate verification assigns counts to hosts or architectures.
Distributed callers also provide `--shard-index I`, where `0 <= I < N`. `matrix`
emits only shard indices and the total shard count; `verify` audits all reports
without rerunning tests. `--workers` applies only to `run`. For example:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test python scripts/native_e2e.py run \
  --shards 3 --workers 1 --output-dir /tmp/spa-native-e2e-002
```

Release dispatches expose an optional `shards` input, which overrides repository
variable `SPA_E2E_SHARDS`; automatic runs use that variable when set. Leave it unset
to follow the shared default instead of maintaining a second default. Each runner
service supplies its own `SPA_E2E_WORKERS` environment value. A repository variable
does not set or override worker capacity. An eligible runner can receive any shard
and take another when it finishes.
The existing private group and generic `self-hosted` / `linux` labels determine
eligible runners; no per-shard routing labels or CPU architecture rules are needed.

The runner isolates shard workspaces and retains the existing per-invocation native
user folders. It records original IDs and outcomes, JUnit, target identity, resource
configuration, and elapsed shard time. Each report's actual worker count is checked
against its pytest execution evidence, independently of other runners' counts.
Every worker must collect the same suite and
assigned shard. Success requires every shard, one outcome per selected ID, identical
full collections and targets, successful pytest exits, and nonempty JUnit reports.
A shard may contain only documented platform skips; the complete selection must
execute tests. Missing, duplicate, cancelled, or mismatched evidence fails the aggregate.
Ambient `PYTEST_ADDOPTS` is cleared so it cannot silently reduce required coverage.
The entry point is for macOS and Linux; extra diagnostic pytest options belong in
an explicit direct pytest run.

Run the full real-runtime tier, including complete example rebuilds, with:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test pytest -m e2e -x -vv --tb=short -rs
```

Use `-rs` so platform and environment skips remain visible. Use collection output when
moving tests to confirm that parametrized cases were preserved:

```sh
uv run --frozen --group test pytest --collect-only -q
```

### Observe native failures during execution

Start with affected representative native cases. Keep the active output visible,
investigate the first failure, and rerun the failed cases after the fix before wider
regression. Do not leave a failing native suite running while waiting for a human to
report a crash dialog.

Documented local native commands and the shared native runner use pytest's
`-x` to stop after the first failed test, `-vv` to identify each result as it arrives,
and `--tb=short` to retain concise failure details. Expected rejection and controlled
failure tests that satisfy their assertions pass normally and do not stop the run.
Within the failing shard, already-running tests can finish during xdist shutdown,
and another native invocation can occur before workers stop. The failing test name is
visible when its report arrives; the final traceback and JUnit report follow worker
shutdown. Local execution cancels outstanding sibling shards and cleans up their
owned workers and native children. The CI matrix uses fail-fast cancellation. Neither
path monitors OS crash dialogs, and a cancelled sibling is not successful evidence.

The existing Runtime Integration failure reports preserve the process exit status
and available stdout/stderr; signal termination includes the number and the host's
signal name when known. Direct native fixtures retain the same process evidence in
their assertions through `tests.support.process_diagnostics`. Use that helper when
adding a captured direct subprocess check. If a fixture's preliminary probe raises an
uncaught `RuntimeIssue`, `tests/conftest.py` attaches its diagnostics through pytest's
report hook as an exception note for the normal traceback and JUnit report. Expected
exceptions handled by a passing test do not reach that hook as failures. Do not infer a signal
from an ordinary positive exit status, or replace a test failure with a skip.

When saving logs, also stream them to the terminal and preserve the failing exit code.
For Bash or zsh:

```bash
set -o pipefail
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test python scripts/native_e2e.py run \
  --output-dir /tmp/spa-native-e2e-003 2>&1 | tee native-e2e.log
```

For a deliberate diagnostic run that collects all failures, invoke pytest directly
with `-m "e2e and not slow" --maxfail=0 -vv --tb=short -rs`. That choice does not
change the shared gate. A stopped run remains failed even if its partial JUnit report
records executed tests. The shared runner
keeps pytest's nonzero result, still audits the report for missing/empty/all-skipped
execution, and the workflows retain JUnit evidence on failure. Passing cases from a
partial run do not establish full-suite verification.

### Source checks

Run the same source checks used by CI with:

```sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen python scripts/lua_quality.py
```

`pyright` checks production code under `src/`. Runtime tests deliberately construct
invalid and partially controlled values, so their correctness is enforced by pytest
instead of the production type gate.

The Lua gate covers every tracked `*.lua` file, including production scripts and test
fixtures. Install the Luacheck and StyLua versions pinned in
`.github/actions/setup-lua-quality/action.yml` on your `PATH`. Run only the Lua linter
with `uv run --frozen python scripts/lua_quality.py lint`, or format the Lua baseline
with `uv run --frozen python scripts/lua_quality.py format`. The default command runs
Luacheck and StyLua in check mode. Luacheck checks Lua syntax and known globals;
StyLua checks formatting. Neither check verifies Aseprite API members or native
behavior. Use the real-runtime E2E tier for that evidence.

## CI gates

`.github/workflows/ci.yml` runs on every pull request and manual dispatch. PR runs
test GitHub's temporary merge result. The main ruleset requires the three checks
below and an up-to-date branch before merging; a main push does not repeat routine
CI. Release maintenance also dispatches CI for its resulting PR head unless the
latest manual CI run for that same branch and SHA already passed. These routine
jobs use Python 3.13, uv 0.11.19, and the committed `uv.lock` with `--frozen`. They
do not set up Aseprite or run native E2E.

| Job | Required evidence |
| --- | --- |
| Source quality | Ruff lint and formatting, Pyright for production source, and Luacheck plus StyLua for all tracked Lua. |
| Fast tests | Unit and integration tests selected with `-m "not e2e"`, in one job with four pytest workers by default. |
| Build and smoke test distributions | One sdist and wheel, valid package metadata, and a successful `spa version` from a wheel-only environment populated from locked runtime dependencies. |

A failure in any job fails routine CI. These three job names can be required checks
when branch protection is available. Their success does **not** establish Linux
native execution. There is no maintenance selector or skipped native job in CI.

### Release-only native execution

Only `.github/workflows/release.yml` from `refs/heads/main` can admit jobs to the
private `spa-release` runner group. Routine PR CI remains on GitHub-hosted runners.
PR events, other caller workflows, forks, schedules and non-main dispatches cannot
use this native path. The retained `native-e2e.yml` workflow remains disabled; its
old PR/main target resolver is not an admission route to the Release runners.

The reusable `native-e2e-shards.yml` first runs admission on a GitHub-hosted runner.
Its inline code checks GitHub's caller repository, workflow file/ref, event and
branch before any target checkout. It accepts only `kind=release` and a full SHA.
For an automatic release, it reads the Release ID returned by this run's draft job,
requires that record's `target_commitish` to equal the target SHA, and checks that commit against the
original main event's history. It never looks up the latest release or current main
head. Manual Release verification uses the original event SHA and does not publish.
A rejection fails admission and prevents all self-hosted jobs from being scheduled.

The native jobs depend on admission. They load CI actions from the admitted caller's
original workflow commit, then check out the validated test target in `native-target/`.
Python dependencies, the wheel, test collection and execution use that target directory.
This prevents an older Release's local actions from restoring the retired cache path;
CI tooling and tested source have separate owners and checkouts.
The final hosted aggregate requires quality and every shard to succeed, then audits
complete exact-SHA reports. Failed, skipped, cancelled, empty, stale or incomplete
evidence cannot authorize publication. GitHub-hosted jobs retain release credentials;
the native runner receives only read access to repository contents.

### Complete example rebuilds

| Trigger | Real-runtime selection |
| --- | --- |
| Routine PR update or manual CI | None; source, fast-test and distribution checks only. |
| Automatic or main-dispatched Release verification | `e2e and not slow` at the exact release SHA; manual runs do not publish. |

The shared `scripts/native_e2e.py` owns the native selection. The Linux action
checks the host-provisioned runtime and prepares the wheel, then calls it for one shard. This retains the
project and wheel-installed CLI paths, real
`--batch --script` probe, both small wizard probes, hidden-pixel regressions and
all other native assertions. The owner removed both complete example rebuilds
from automated gates on 2026-09-28 after reviewing their measured cost. Full native
verification means the required tool suite, without regenerating example deliveries.
For complete asset reproducibility after an example change, use its build/verify
commands or run locally:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest -m "e2e and slow" -x -vv --tb=short -rs
```

These checks compare full deliveries and hidden native pixels. They remain
separate, explicit local evidence.

### Verify CI changes locally first

Before pushing workflow changes, run the source checks above, `actionlint`, and the
focused workflow regressions:

```sh
actionlint
uv run --frozen --group test pytest tests/ci tests/release -q
```

`actionlint` checks workflow structure and expressions; install ShellCheck alongside
it to check embedded shell too. It does not validate composite actions, so also
inspect changed composite YAML and run its shell/behavior checks. The regression
suite executes the actual workflow/action shell with real Git and controlled GitHub
responses. These tests do not establish runner-group enforcement, token permissions
or Linux native execution.

Run affected native tests locally before requesting Linux verification. For CI
infrastructure, resolve syntax, shell and branch/dispatch logic locally first.
Use a small hosted probe only for a remaining platform-specific hypothesis, then
one final native run when the change has converged. Do not run the whole suite on
every diagnostic push. For an unchanged Release target, rerun only failed jobs; a changed
source requires a new run and a complete shard set. macOS results remain
macOS evidence. `act` can help with shell/container checks, but does not reproduce
all GitHub permissions, concurrency or timeout behavior; see its
[unsupported features](https://nektosact.com/not_supported.html).

### Verification time limits

The owner limits remain **20 minutes for routine CI**, **40 minutes for full
manual/periodic verification**, and **40 minutes for Release verification**.
GitHub's native job timeouts enforce the allocation. The three parallel routine jobs
retain their smaller 10-minute limits. Release verification allocates **1 minute
preparation + 1 minute hosted admission + a 35-minute shard job limit + 3 minutes
aggregation**. Its 10-minute quality/package job runs alongside admission
and the shards. All job steps count, including checkout, setup, tests and uploads.
Unused allocations do not transfer between jobs.
There is no compilation deduction, larger outer timeout, or second clock. Parallel
jobs reduce elapsed time but runner capacity still bounds concurrency.

With more shards than runners, multiple jobs run in sequence on each runner. The job
limits do not add up to a workflow-wide timeout; measure the complete verification,
including queued jobs, against the unchanged 40-minute budget.
Release has separate draft and publication jobs. A failed or timed-out verification
job prevents publication. The [issue #107 evidence](evidence/issue-107-ci-capacity.md)
records historical measurements and superseded cache experiments.

### Release runner setup

Use an organization runner group named `spa-release` with these settings:

- Selected repository: `aigengame/aseprite-automation`; allow this public repository.
- Selected workflow only:
  `aigengame/aseprite-automation/.github/workflows/native-e2e-shards.yml@refs/heads/main`.
- Linux runners in this group, carrying the `self-hosted` and `linux` labels.
  Labels route jobs; the group's repository/workflow restrictions control access.

Protect main and review changes to workflows, actions, scripts and tested code.
Admission trusts reviewed main code: it cannot make malicious code merged by a
maintainer safe. Do not grant this group to all workflows or PR refs. The group
restriction is an external prerequisite, not something a YAML label can enforce.
See GitHub's [runner-group access documentation](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/manage-access).

Provision the runner as a dedicated, non-root account on a Linux host with Git,
Git LFS, Python 3, Bash and the runtime's shared libraries. The account needs a
writable workspace and outbound access for Actions, repository/LFS checkout and
locked Python dependencies. The action installs uv and managed Python 3.13; it
neither runs sudo nor installs operating-system libraries.

Install Aseprite privately outside the checkout, runner temporary directory and
cache paths. Set `SPA_TEST_ASEPRITE` in each runner service's environment to the
absolute executable path. The action requires no display, checks `--batch --version`
and a real `--batch --script` result before installing SPA or starting tests. A
missing or unusable runtime fails without a download, build or cache fallback.
Aseprite installation, libraries and upgrades remain host administration tasks.

The workflow uploads only native `result.json`, `pytest.json` and `junit.xml`
reports. It never uploads or caches Aseprite. The retained `aseprite-build.yml`
now fails with provisioning instructions even if manually re-enabled.
Python dependency caching is separate and does not contain the native installation.

Each runner service executes one shard job at a time, with its own worker count,
and takes queued shards through GitHub's native queue. Do not bind shard indices or
worker counts to architectures or runner labels.
More eligible services can take queued jobs without a new scheduler.

At main commit `2daa7f36cfa550313562c80bb539ca827b678be0`, the same complete selection
produced 2,376 passed and 11 skipped in each measured configuration:

| Shards | Complete verification | Preparation summed across jobs |
| --- | --- | --- |
| [4](https://github.com/aigengame/aseprite-automation/actions/runs/38019562706) | 34:03 | 100.3 s |
| [6](https://github.com/aigengame/aseprite-automation/actions/runs/38021643557) | 34:42 | 130.4 s |
| [8](https://github.com/aigengame/aseprite-automation/actions/runs/38023909556) | 32:14 | 164.6 s |

Eight shards reduced elapsed time by 5.3% versus four and 7.1% versus six, while
remaining inside the 40-minute budget. Preparation is included in elapsed time;
its sum measures resource use across concurrent jobs. These are single sequential
trials, not a guaranteed speedup or job distribution. Keep both counts configurable.

Before adding Aseprite, register the runner in this group and validate access with
harmless jobs: the allowed reusable workflow from main must route correctly, while
a PR/fork, another workflow and a dev dispatch must not reach the private runner.
Confirm the group's actual selected repository and full workflow ref, not only the
counts shown in its settings page. Local regression tests cannot prove this GitHub
scheduler boundary. Complete that deployment check before enabling native releases.

### Restore the Aseprite runtime

Repair the installation or service environment on the host, then rerun the original
failed Release jobs. Keep its original event, release target and shard configuration;
successful shard reports can be reused only for that same target and configuration.
The aggregate still requires a complete set. A host repair is not SPA test evidence.

```sh
gh run rerun <failed-release-run-id> --failed
```

Do not resolve current main or a newer Release during recovery. Do not rerun all jobs
and ask release-please to create the same draft again. Workflows predating this
runner migration retain their old execution code; they are not a route to restore
binary builds or caches. Reconcile such a pending release with the owner.

## Platform and display requirements

Verification tier, host platform, and display capability are separate properties.
Place a platform condition on the smallest test that needs it. A passing macOS test is
macOS evidence; it is not Linux evidence. The macOS bundle and restricted-agent cases
remain macOS-specific. Issue #69 owns Linux CI and Linux real-Aseprite evidence.
CI runs the fast tier only on Linux. Thus these fast cases give local evidence only:
`tests/runtime/test_integration_windows_capture.py` and the Windows interruption case
of `tests/ci/test_integration_native_shards.py` (Windows),
`tests/runtime/test_integration_aseprite.py::test_unwritable_bundle_link_has_typed_start_failure`
(macOS), and the case-variant cases of
`tests/application/test_unit_publication_identity.py` (a case-insensitive file system).

Aseprite `--batch` does not start the UI. A test that produces or inspects image files
through that path is not windowed unless it actually needs a display. When a
test requires a window, declare that precondition at the test boundary and add a
shared display gate only when more than one test needs it. An optional run on a host
without display capability can skip with a visible reason. Display permission denial
must fail. A job that claims graphical coverage must fail when its required windowed
tests do not execute.

The [wizard example](../examples/wizard_cast/README.md) has two real-runtime tests:
a small component geometry proof and one complete fresh build against the checked-in
delivery. Fetch its Git LFS assets before this local
check. The full build is marked `e2e` and `slow` and follows the opt-in policy above.
A reference macOS build takes about four minutes; one
Linux CI observation took 329.6 seconds, compared with 6.7 seconds for the small
probe. These are measurements, not time limits. Explicit double builds remain
available through the example's `verify` command, with retained local evidence.
The test does not start Godot. The example's separate Godot tests and local
windowed/package evidence are documented beside it and are not claimed by Linux CI.

The Release host supplies Aseprite and its runtime libraries. Verification checks
that both `DISPLAY` and `WAYLAND_DISPLAY` are absent, installs the current wheel in a
separate environment on each shard, and runs the shared real-runtime entry point.
Each shard writes JUnit and original-ID reports. The aggregate checks the full
selection, including missing/zero/all-skipped execution. The job summary records
the tested commit, trigger, executable, Aseprite version, selected scope, display
state and exercised path. A macOS-only skip remains visible and does not invalidate
Linux batch evidence while other E2E tests execute.

The Linux real Aseprite job is also part of release verification. A release workflow
always reruns the required native suite, excluding complete example rebuilds, at the exact release commit
and does not reuse a generally green CI or weekly run. A successful macOS local run
remains separate developer evidence; it cannot replace the Linux release gate.
Windowed Aseprite behavior has no CI coverage until a
dedicated display-capable job is added with an execution-count gate.

The [hybrid wizard example](../examples/wizard_cast_v2/README.md) uses frozen local
imagegen inputs. Its routine probe is an `e2e` test. Its full test is also marked
`slow`: one fresh build must match the retained v2 delivery. This complete rebuild
runs locally on demand. Automated tests need no imagegen service or generation
credentials. macOS build cost and Godot evidence are recorded separately in the v2
example's dogfooding report; Linux asset CI does not establish graphical or gameplay
acceptance.

## Local windowed Tilemap Filter comparison

`python -m tests.filter.windowed` prepares and verifies seven operator-assisted
cases for #152. It is explicit local acceptance evidence, outside pytest collection
and headless CI. A running windowed Aseprite with scripting and a usable display is
required. Missing output, rejected access, failed assertions, or differing reopened
pixels fail this requested comparison; none count as a skip or pass.

Use the same installed Aseprite binary for preparation, the window, and verification:

```sh
export SPA_TEST_ASEPRITE=/absolute/path/to/aseprite
uv run --frozen --group test python -m tests.filter.windowed prepare /absolute/new/evidence-dir
```

The output directory must not exist. Preparation reuses the native batch fixtures,
records Source hashes, and produces independent SPA expected outputs. Cases cover
RGB, Grayscale, Indexed, RGB Palette colors, shared Tiles across linked/distinct Cel
Images, and a partial Canvas Selection over offset rectangular Tiles with diagonal
placement flags. The last case also retains Empty and unused Tiles. Comparisons
observe all fixture placement pixels, Tile pixels/data, Palette Changes, and
resolved colors after reopening. They do not replace the batch metadata,
rollback, state-restoration, or broader parameter matrix tests.

In Aseprite:

1. Select **Tileset Mode: Manual**. Open **View → Run Command**, enter
   `@app.command.DeveloperConsole()`, and press Enter.
2. For each case directory, execute `dofile("/absolute/new/evidence-dir/CASE/run.lua")`.
   Allow the generated Source/output/receipt file accesses when prompted. Full trust
   or changes to script security settings are unnecessary.
3. The script opens only the generated Source, sets the Canvas Selection and target
   state, and checks observed Layers, Cels, Frames, Palette Picks, and Manual mode.
   Timeline must be visible for a selected range. The helper opens it explicitly.
   JSON arrays must be copied into Lua tables before assigning `app.range.frames`.
4. In the real **Brightness/Contrast** dialog, enter **Brightness 50**, leave
   **Contrast 0**, verify **Cels: Selected**, and enable **Preview**. Only **R** is
   enabled for RGB/Indexed and **Gray** for Grayscale; Alpha is disabled. Retain a
   screenshot of these settings and the visible target state. Click **OK** once;
   do not click Apply. The script saves, closes, and reopens its output.
5. Confirm that the script finishes without an error. Repeat for all seven cases.
   Close any generated document left by a failed run before starting a fresh run.

Windowed Color Bar Palette Picks and an enabled Timeline range are alternative native
sites. Therefore the Palette-color case targets the active Cel at Frame 2 in both
SPA and UI. The RGB, Grayscale, and Indexed cases use the Frame 2 Palette basis and
target Frame 1. The sharing and spatial cases use the Frame 1 basis. The batch suite
separately covers Palette-color application with a distinct target Frame; this local
windowed comparison makes no claim about simultaneously selecting both sites.

```sh
uv run --frozen --group test python -m tests.filter.windowed verify /absolute/new/evidence-dir
```

Verification removes the previous `comparison.json` before reading the manifest and
checking cases. It writes a new report only after all seven comparisons pass, so a
failed comparison cannot leave a previous aggregate success report in place.

Retain `manifest.json`, `comparison.json`, case receipts, screenshots/operator
observations, Source and both outputs with the PR evidence. A receipt records the
script's observed preconditions and reopen; it alone cannot prove that an operator
inspected the dialog or pressed OK. Equality plus unchanged Source hashes is the
persisted-data check. Cancel/no-op and repeated Apply are detected by the nonzero
fixtures. Record the actual GUI Aseprite version and host; do not report these local
results as Linux or automated CI coverage. Restore the prior Timeline visibility
and Tileset mode after completing the local session if they were changed.

## Test quality checks

These checks get the evidence that the [test standards](test-standards.md) ask for.
The commands are for a POSIX shell on macOS or Linux. Run them in the project
environment ([routine commands](#routine-verification-commands)).

### Mutant check

A mutant is the code under test, made wrong on purpose. A test that passes against it
cannot find that defect.

1. Run `git status --short -- src`. If it shows a change, save a copy of the file first.
2. Find the line in `src/` that the claim of the test depends on. For a Kernel rule, the
   line can be in a Lua file under `src/spa/kernel/`.
3. Change only that line to the wrong behavior that the test must find. Keep the path of
   the result, and change only the fact that the test claims.
4. Remove the bytecode cache:

   ```sh
   find src tests -name __pycache__ -prune -exec rm -rf {} +
   ```

   CPython uses a cached `.pyc` file when the source has the same size and the same
   modification time in whole seconds. A mutant of the same length that you make in the
   same second then does not run.
5. Make sure that `SPA_TEST_INSTALLED_CLI` is not set. A wheel-installed CLI does not
   run the code of your checkout.
6. Run the test. It must fail. When the test replaces an old test, run the old test
   against the same mutant too.
7. Read the `E` line of the failure. It must be the assertion of the claim. These do not
   show that the test finds the defect:
   - an import error or a crash;
   - a `runtime_incompatible` failure from the runtime probe. A mutant in a Lua module
     that the probe loads stops the probe. Change the handler entry file instead;
   - a failure that the old test and the new test both have. Such a mutant does not
     show a difference between them. Choose a mutant that keeps the failure path.
8. When the mutant does not change the result for the input of the test, it is an
   equivalent mutant. Choose another mutant.
9. Restore the file from Git or from your copy, and remove the cache again. Make sure
   that `git status --short -- src` shows what it showed in step 1.
10. Record each mutant, the result of the old test and the result of the new test in the
    pull request description. When no mutant can isolate a check, write that under "Not
    verified".

### Stand-in Aseprite run

The stand-in is an executable that forwards the runtime probe to the real Aseprite. It
records the test that makes a Kernel call, and it fails that call with exit status 1. It
runs every other call, for example a Lua fixture, with the real Aseprite. An e2e test
that passes on the stand-in with no Kernel call did not need the Kernel.

The stand-in tells the calls apart by their arguments. The probe runs the packaged
`runtime/probe.lua`. The probe and each Kernel call pass a script parameter `request=`,
so the stand-in checks for the probe first. A Lua fixture can pass `response=`, so that
argument does not identify a Kernel call.

1. Set `SPA_TEST_ASEPRITE` to your real Aseprite executable. Make the stand-in:

   ```sh
   standin_dir=$(mktemp -d)
   real_aseprite=$(realpath "$SPA_TEST_ASEPRITE")
   for resource_dir in "${real_aseprite%/*}/../Resources/data" \
     "${real_aseprite%/*}/../data" "${real_aseprite%/*}/data"; do
     if [ -f "$resource_dir/gui.xml" ]; then
       ln -s "$(realpath "$resource_dir")" "$standin_dir/data"
       break
     fi
   done
   cat > "$standin_dir/aseprite" <<EOS
   #!/bin/sh
   case " \$* " in
     */runtime/probe.lua*) exec "$real_aseprite" "\$@" ;;
     *" request="*)
       printf '%s\n' "\$PYTEST_CURRENT_TEST" >> "$standin_dir/calls.log"
       exit 1 ;;
     *) exec "$real_aseprite" "\$@" ;;
   esac
   EOS
   chmod +x "$standin_dir/aseprite"
   ```

   The stand-in must be a regular file. Runtime discovery looks for `data/gui.xml`
   next to it, so the loop links the `data` directory of the real Aseprite there.
2. Run the e2e tier against the stand-in, with a summary line for each passed case:

   ```sh
   SPA_TEST_ASEPRITE="$standin_dir/aseprite" uv run --frozen --group test \
     pytest -m "e2e and not slow" -n 0 -rp > "$standin_dir/run.txt"
   ```

   On macOS, an Aseprite launch can stop before its script runs. When a case stops,
   run it again alone.
3. Compare the passed cases with the cases that made a Kernel call:

   ```sh
   sed -n 's/^PASSED //p' "$standin_dir/run.txt" | LC_ALL=C sort -u \
     > "$standin_dir/passed.txt"
   sed 's/ ([a-z]*)$//' "$standin_dir/calls.log" | LC_ALL=C sort -u \
     > "$standin_dir/called.txt"
   # Passed, no Kernel call:
   LC_ALL=C comm -23 "$standin_dir/passed.txt" "$standin_dir/called.txt"
   # Passed, Kernel called:
   LC_ALL=C comm -12 "$standin_dir/passed.txt" "$standin_dir/called.txt"
   ```

4. Examine each listed case:
   - Passed with no Kernel call: the test did not need the Kernel. When its claim is
     the runtime probe, a caller-owned Lua script or a behavior of Aseprite itself, it
     stays in the e2e tier.
     Otherwise delete it when a fast test holds its claim, or move it to the fast tier.
     Read its Lua fixture first: a fixture that runs a Kernel handler with `dofile`
     passes no `request=` argument, so the stand-in does not see that Kernel call.
   - Passed with a Kernel call: the test does not check what the Kernel did. Assert a
     fact that only a real run gives. A test that asserts that the Kernel call fails
     passes here correctly.

The run has limits:

- A process that does not get `PYTEST_CURRENT_TEST` from pytest, for example an MCP
  server process, writes an empty line to the log. The log does not name the case of
  that Kernel call.
- The run lists only cases that pass. A test that fails on the stand-in for an unrelated
  reason, for example an error in a test helper, is not in the lists. Read why such a
  case fails.
