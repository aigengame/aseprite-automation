# Test suite

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

## Ownership areas

| Directory | Behavior owner |
| --- | --- |
| `tests/application/` | Application orchestration, including compatibility checks before Operation execution. |
| `tests/ci/` | CI target selection, native test execution policy, and pre-merge evidence checks. |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/color_mode/` | Conditional Color Mode choices, native mapping/Dithering, complete Sprite and Plan conversion evidence. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration and Operation Descriptor constraints. |
| `tests/export/` | Image Export contract, PNG Artifact verification and publication, and real Aseprite output evidence. |
| `tests/examples/` | Installed-CLI workflows, deterministic asset production, and checked-in downstream asset agreement. |
| `tests/frame/` | Frame timing, insertion, Cel copy/link intent, Tag adjustment, and native persistence. |
| `tests/filter/` | Native Filter application, Channels, Cel targets, Palette basis, state restoration, and verified publication. |
| `tests/layer/` | Layer hierarchy, exact addressing, and native addition evidence. |
| `tests/motion/` | Bounded Cel curve sampling, complete preflight, and persisted pixel/property preservation. |
| `tests/paint/` | Paint Domain Module contract, bounded mutation evidence, and native Pixel Patch behavior. |
| `tests/palette/` | Shared Effective Palette resolution over native Frame-based Palette Changes. |
| `tests/plan/` | Static Plan preflight, single-Sprite Step composition, and commit gates. |
| `tests/release/` | Release metadata and publication gates. |
| `tests/runtime/` | Aseprite Runtime Integration, including discovery, launch, private Kernel transport, and real-runtime evidence. |
| `tests/sprite/` | Sprite Domain Module contracts plus real creation, copy, flatten, bounded validation, persisted reopen, structural inspection, and Target Commit evidence. |
| `tests/tag/` | Tag stored facts, exact current addressing, native mutation, and save/reopen evidence. |
| `tests/slice/` | Complete Slice Keys and coverage, exact addressing, bounded native authoring, exporter validation, and save/reopen evidence. |

Add an ownership directory only when tests for that behavior exist. Keep a helper in
the narrowest ownership directory that uses it. Move a helper to `tests/support.py`
only when more than one ownership area needs it. Each directory is a Python package,
so different owners can safely use the same focused file name later.

Native Paint #26 has separate Line, Rectangle, and Ellipse runtime gates. Its
real-runtime suite compares saved pixels with direct `app.useTool` references for
all four color-paint Inks at opacity 0, 128, and 255. It also covers native Brush
footprints, degenerate shapes, RGB/Grayscale/Indexed (including transparent index 7),
Background and linked Cels, off-canvas Cel placement, explicit Selection, refusal
without publication, post-write save/reopen failure, and state restoration after
success and failure. These tests
use `--batch --script` and require no display. They establish batch native pixel
parity; they do not certify windowed UI interactions. Run the focused slice with:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/paint -x -vv --tb=short -rs
```

Native Paint #28 adds independent Contour and Blur gates. Contour tests compare
complete ordered gestures, degenerates, repeated Points, both Freehand Algorithms,
and all four color-paint Inks at opacity 0, 128, and 255. Blur tests compare native
effect pixels across four Tiled Modes, three opacities, both algorithms, and all
three Color Modes, including offset linked Cels and Frame-varying Palettes. A
same-process fixture verifies ambient state and file preservation after success,
bounds rejection, an injected failure after native invocation, and failed reopen.
Discovery tests require the version-specific Gradient Capability Gap and callable
Contour/Blur without invoking Gradient's unsafe headless Context Bar path. This
delivery combination follows issue #28; it does not establish a callable Gradient.

Change Color Mode #33 compares conversion output with independent native
`app.command.ChangePixelFormat` calls for every RGB Map and Color Best Fit choice,
To Gray choice, Dithering algorithm, and Factor boundaries. Fixtures include
Frame-varying Palettes, Alpha/Transparent Color Index, Background and linked Cels,
Tilemaps, and unreferenced Tilesets. Tests cover all source/target pairs, typed
Matrix resolution failures, standalone/Plan parity, in-place intent, rollback, and
save/close/reopen. These are batch tests and require no windowed graphics session.

Brightness/Contrast #35 covers RGB/Grayscale/Indexed pixels, Indexed Palette-only,
and RGB Palette plus matching pixels. Native fixtures verify component Alpha
preservation separately from Indexed RGB Map quantization, Cartesian targets,
Linked Cel Image deduplication, Selection, Palette basis, and exact Palette Changes.
Tilemap pixel targets require the explicit Manual extension delivered by #152;
without it, the whole pixel application is refused. Palette-only Tilemap anchors
preserve ordinary Images, placement bytes, and all Tile bitmaps including Empty
Tile 0. Direct native calls supply boundary-value parity; injected post-command
failures verify transaction rollback and active Sprite, range, Palette Picks, and
Selection restoration. All cases use batch scripting without a graphical display.

## Verification tiers

Use the tier in the file name:

- `test_unit_*.py` exercises rules and contracts in one process.
- `test_integration_*.py` connects SPA components. It can invoke the installed `spa`
  CLI with a controlled fake Aseprite executable, but it does not prove native
  Aseprite behavior.
- `test_e2e_*.py` invokes the installed `spa` CLI with a real Aseprite executable,
  or exercises a shared packaged Kernel Interface directly with native fixtures.
  Mark the module or each test with `pytest.mark.e2e`.

`pytest.mark.slow` is an additional cost marker, not a verification tier. Use it
for complete example rebuilds, which run locally on demand. Automated CI and
Release exclude these tests. The small wizard probes remain only `e2e`.

Runtime integration fixtures cover incompatible Lua and API observations and structured
failure without claiming native execution. Real-runtime tests execute the packaged
probe and assert its observed embedded Lua version, `app.apiVersion`, JSON round trip,
file I/O, and scripting evidence. These three facilities are prerequisites of a complete
probe response. Runtime capabilities are reported independently: omitting a known
capability does not invalidate the probe, while the Application rejects it before
execution when the selected Descriptor requires it. Each later Operation adds
real-runtime evidence for the native capabilities named by its Descriptor.
The Sprite E2E fixture covers nonempty Frames, Tags, Palettes, nested Layers, Cels,
Slices, and Tilesets in addition to empty-section and unrequested-section semantics.
The Palette fixture checks the shared resolver before, at, and after a Palette Change,
with literal expected Frame and color facts and unrelated active editor state. Operation
E2E tests retain coverage of caller-specific validation, resource loading, and publication.
Slice inspection uses Aseprite's native sprite-sheet metadata export to observe the
complete ordered Key list, converts its zero-based Frames to the public one-based model,
and combines it with public Slice text and color data. The private metadata stays in
the invocation workspace; the reader requests no texture output. The Slice suite
uses native fixtures plus test-only file-format construction for multi-Key input
that public Lua cannot create. Product handlers never patch the file format.
`test_e2e_vendor.py` wraps the native export boundary to check malformed and stale
metadata refusal. `test_e2e_slice.py` verifies CLI addressing, complete Frame
coverage, static geometry, metadata-only edits on animated Slices, whole deletion,
reopened addresses, custom property retention, and failure without Target publication.
The runtime probe separately checks whole-Slice add/set/remove with real
save/close/reopen. These are batch tests on local macOS and Linux CI; they make no
windowed GUI claim. See [Slice evidence](evidence/issue-40-slices.md).
The Export Image E2E fixtures cover native visible Layer composition, RGB Alpha
values, no-profile and sRGB files, unsupported source modes, Tilemap Images on visible
and hidden Layers, unsupported Color Profiles, and explicit replacement. A wheel-installed
test verifies the packaged Export handler and Pillow decoder on Linux CI.
Paint E2E cases reject direct and two-link Source aliases for both `in_place` values
without a Target Commit. Static integration cases confirm rejection before the
runtime probe. A real Aseprite case accepts explicit in-place Paint through two path
spellings of the same publication entry. On a case-insensitive filesystem, real
Paint cases also check file-name case variants under both `in_place` values.
Plan E2E cases cover read-only composition, create/paint/get on one live Sprite,
failed-Step and failed-Postcondition publication gates, and in-place failure
preserving the original file digest. A wheel-installed case verifies the packaged
Plan handler. Static Plan checks execute without Aseprite and report missing Source,
invalid Target parent, and existing Target conflicts. A controlled transport case
verifies one process and typed failed-Step evidence; the real runtime verifies the
shared capability probe before Plan Steps.
Plan preflight also rejects Source aliases that would be replaced by Target Commit and
Postconditions that contradict a first Sprite creation Step. Real Aseprite cases
verify alias rejection with both `in_place` values, same-entry in-place success, and
that a document-dependent Postcondition failure leaves the Target absent.
Aggregate discovery conservatively requires every eligible Plan Step capability;
the Plan execution gate checks selected Step requirements plus mandatory final Sprite
inspection in its one Aseprite process.
The Cel Plan tests compare standalone and Plan properties, linked Image facts, and
stored pixels for hidden and zero-opacity Cels. A CLI subprocess fixture observes
the real invocation and commit adapters and injects invalid native evidence to test
the publication gate. The bounded [Cel Plan profile](evidence/issue-105-profile.md)
records one fixed wizard workload, stage timings, and its measurement limits.

Motion tests use generated wizard poses and a floating emblem. Native inspection
compares every stored pixel, including alpha-zero values, in RGB, Grayscale, and
Indexed fixtures with transparent index 7. Cases cover exact rational sampling,
all interpolation/rounding policies, signed position boundaries, missing and linked
targets, whole-range refusal, and 65 existing targets without a Plan-Step quota.
Plan cases verify Step-start baselines, multiple Layers, later Paint/Frame edits,
one native invocation and Target Commit, and rejected incomplete/contradictory
evidence. [Motion measurements](evidence/issue-104-motion-performance.md) retain
the real persisted verification path; visual continuity remains a human check.

The initial evidence profiles use local macOS Aseprite 1.3.18.5-dev and the pinned
Linux CI Aseprite 1.3.18.5 source release. Both expose `_VERSION == "Lua 5.4"` and
`app.apiVersion == 41`; the macOS build's vendored Lua 5.4.6 records source provenance,
not a patch-level compatibility rule. The E2E assertion pins this evidence family while
the runtime compatibility decision continues to use the Descriptor's observed language
and API requirements.
This pin verifies the current baseline and selected host execution profiles; it does
not certify each later Aseprite release. Do not require an additional version test
solely because another native release exists. An observed defect or newly accepted
requirement warrants a targeted check of the affected Operation.

Pytest rejects unregistered markers. The root e2e gate also rejects a selected e2e
test when `SPA_TEST_ASEPRITE` is absent, is not a file, or is not executable. A missing
runtime therefore cannot produce an all-skipped successful e2e run.

Run the fast unit and integration tiers with:

```sh
uv run --frozen --group test pytest -m "not e2e"
```

Run the complete routine real-runtime selection, including the small wizard probes,
through the same entry point used by Native E2E and Release:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test python scripts/native_e2e.py run \
  --output-dir /tmp/spa-native-e2e-001
```

Use a new output directory for each run. For complete installed-wheel CLI coverage,
build the current wheel, install it with the locked runtime dependencies in a separate
environment, and set `SPA_TEST_INSTALLED_CLI` to that environment's `bin/spa`. Otherwise
the existing wheel-only cases report their environment skips.

### Shared native parallel execution

`scripts/native_e2e.py` owns selection, configuration, partitioning, execution, and
report validation for local, Native E2E, and Release callers. Its initial defaults
are **2 shards × 2 pytest workers per shard**. Local execution starts the shards on
one machine; `.github/workflows/native-e2e-shards.yml` places the same shards on
separate Linux runners. Each shard uses xdist's `load` scheduler. Pytest collects the
full `e2e and not slow` selection, sorts the original node IDs, and assigns each ID
by its ordinal modulo the shard count. No file lists or timing database are needed.

Override resources with `--shards N --workers N`, or `SPA_E2E_SHARDS` and
`SPA_E2E_WORKERS`. Explicit arguments take precedence; empty environment values use
the shared defaults. Counts must be positive integers. Distributed callers also
provide `--shard-index I`, where `0 <= I < N`. `matrix` emits the resolved CI matrix;
`verify` audits all reports without rerunning tests. Each subcommand accepts the
same resource options. For example:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test python scripts/native_e2e.py run \
  --shards 3 --workers 1 --output-dir /tmp/spa-native-e2e-002
```

Native E2E and Release dispatches expose optional `shards` and `workers` inputs.
They override repository variables `SPA_E2E_SHARDS` and `SPA_E2E_WORKERS`; unset
values reach the same Python defaults. Scheduled and automatic release runs use
those repository variables. The workflow generates its matrix from this resolved
configuration. Resource changes require no new matrix lists or test policy.

The runner isolates shard workspaces and retains the existing per-invocation native
user folders. It records original IDs and outcomes, JUnit, target identity, resource
configuration, and elapsed shard time. Every worker must collect the same suite and
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
shutdown. Local execution cancels outstanding sibling shard process groups and
cleans up their owned workers. The CI matrix uses fail-fast cancellation. Neither
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

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and
manual dispatch. Release maintenance also dispatches it for the resulting Release
PR head. These routine jobs use Python 3.13, uv 0.11.19, and the committed `uv.lock`
with `--frozen`. They do not set up Aseprite or run native E2E.

| Job | Required evidence |
| --- | --- |
| Source quality | Ruff lint and formatting, Pyright for production source, and Luacheck plus StyLua for all tracked Lua. |
| Fast tests | Unit and integration tests selected with `-m "not e2e"`. |
| Build and smoke test distributions | One sdist and wheel, valid package metadata, and a successful `spa version` from a wheel-only environment populated from locked runtime dependencies. |

A failure in any job fails routine CI. These three job names can be required checks
when branch protection is available. Their success does **not** establish Linux
native execution. There is no maintenance selector or skipped native job in CI.

### Native E2E before merge

`.github/workflows/native-e2e.yml` owns explicit pre-merge Linux verification and
weekly main regression. Target preparation precedes the shared shard matrix, followed
by one unconditional **Linux real Aseprite E2E** aggregate job. It fails if preparation
or any shard did not succeed, then audits the complete original collection and reports.
The main entry below applies after the workflow reaches main. After review and
local checks converge, run it once for the PR:

```sh
gh workflow run native-e2e.yml --ref main -f pr=125
```

In the Actions UI, use **Native E2E → Run workflow**, select main, and enter the PR
number. The workflow resolves the open PR's current base SHA, head SHA and merge
SHA, checks out that exact merge result, and verifies both Git parents before
runtime setup. A conflict, unavailable preview or API failure fails the job.
After native tests, it rechecks the PR and fails if its base, head, merge or open
state changed. The summary and artifacts retain the target, original outcomes, and
per-shard JUnit evidence.
The suite rejects missing/zero/all-skipped execution. An artifact alone is not a
passing result: the workflow and its native job must both succeed.

Immediately before merging, the person or agent doing the merge must compare the
recorded target with the current PR:

```sh
gh api repos/aigengame/aseprite-automation/pulls/125 \
  --jq '{state, base_ref: .base.ref, base: .base.sha, head: .head.sha, merge: .merge_commit_sha}'
```

Require an open PR and an exact match of base ref, base SHA, head SHA and merge
SHA to the successful run, plus the normal review and routine CI checks. Link the
run in the PR. A later head/base update invalidates this evidence; repeat target
preparation and all shards as described in
[recovery](#restore-the-aseprite-runtime), or dispatch a new run. Do not enable
delayed auto-merge with stale native evidence. An unrun,
cancelled, failed or skipped native job cannot admit merge.

This is an explicit merge-process gate. GitHub associates a manual workflow with
its dispatched ref; the green check is **not automatically a required check on
the PR merge SHA**. Do not configure that manual check as though it enforced PR
freshness. The summary's tested target, not the workflow's dispatch SHA, identifies
coverage. See [GitHub event semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).
No status publisher, registry or alternate merge service is introduced.

Leave the PR input empty for a manual main regression:

```sh
gh workflow run native-e2e.yml --ref main
```

This mode rejects any ref other than main and tests its event SHA. The weekly run
uses the same mode, Sunday 19:23 UTC (Monday 03:23 Asia/Shanghai), on the default
branch main. Schedules can be delayed. There is no daily native run or dev schedule;
a normal main push runs only routine CI. A main regression never replaces the PR
merge-result check or exact-release-SHA gate.

Before promotion, the dev entry also requires GitHub workflow registration.
Having the YAML file on dev alone is not sufficient: confirm that
`gh workflow list --all` lists Native E2E and that
`gh workflow view native-e2e.yml --ref dev --yaml` returns its definition.
Only then use `gh workflow run native-e2e.yml --ref dev -f pr=125`, with a cache
visible from dev. A registration result or an accepted dispatch is not a native
test pass. Keep pre-merge acceptance open until the current target finishes
successfully. The bounded #125 rollout is recorded in the
[capacity evidence](evidence/issue-107-ci-capacity.md#native-workflow-registration--2026-09-29).
This provisional entry is not stable-main rollout evidence.

### Complete example rebuilds

| Trigger | Real-runtime selection |
| --- | --- |
| Routine PR update, main push, or manual CI | None; source, fast-test and distribution checks only. |
| Explicit pre-merge Native E2E | `e2e and not slow` at the current PR merge result. |
| Weekly or manual Native E2E on main | `e2e and not slow` at the event's main SHA. |
| Release verification | `e2e and not slow` at the exact release SHA before publication. |

The shared `scripts/native_e2e.py` owns the native selection. The Linux action
prepares the runtime and wheel, then calls it for one shard. This retains the
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
responses. It covers stale PR targets, merge-parent mismatches, main-only routing,
API failures, Release PR head convergence and metadata checks. These tests do not
establish hosted cache visibility, token permissions or Linux native execution.

Run affected native tests locally before requesting Linux verification. For CI
infrastructure, resolve syntax, shell and branch/dispatch logic locally first.
Use a small hosted probe only for a remaining platform-specific hypothesis, then
one final native run when the change has converged. Do not run the whole suite on
every diagnostic push. For an unchanged target, rerun only failed jobs; a changed
PR target requires fresh preparation and all shards. macOS results remain
macOS evidence. `act` can help with shell/container checks, but does not reproduce
all GitHub permissions, concurrency or timeout behavior; see its
[unsupported features](https://nektosact.com/not_supported.html).

### Verification time limits

The owner limits remain **20 minutes for routine CI**, **40 minutes for full
manual/periodic verification**, and **40 minutes for Release verification**.
GitHub's native job timeouts enforce the allocation. The three parallel routine jobs
retain their smaller 10-minute limits. Native E2E allocates **3 minutes preparation
+ 34 minutes for each concurrent shard + 3 minutes aggregation = 40 minutes**.
Release uses the same allocation, with its 10-minute quality/package job running
alongside the shards: `3 + max(34, 10) + 3 = 40`. All job steps count, including
checkout, setup, tests, package checks where present and uploads. There is no
compilation deduction, larger outer timeout, or second clock. Parallel jobs reduce
elapsed time but Actions usage sums their durations; sharding does not promise
lower monthly minutes.

These are running-job limits, not queue-time or whole-pipeline latency promises.
Release has separate draft and publication jobs. A verification overrun prevents
publication. The separate Build Aseprite maintenance job has a 40-minute limit.
The [issue #107 evidence](evidence/issue-107-ci-capacity.md) records measurements
and superseded experiments.

### Restore the Aseprite runtime

Native E2E and Release only
restore an exact Aseprite cache entry. A miss fails before native dependency
installation or compilation and identifies the required key. It does not skip the
native gate or report success. A restored binary must still pass the executable,
resource, version, and real `--batch --script` checks before SPA's E2E suite runs.

To recover:

1. Open **Actions → Build Aseprite → Run workflow** and select the recipe branch.
   Use **main for the stable runtime**. The separate `aseprite-build.yml` runs
   only **Build Aseprite (manual maintenance)** with its own 40-minute native job
   timeout. It validates the pinned source checksum, builds if the exact cache is
   missing, checks the real batch/script path, and saves the verified tree.
2. Confirm that the job succeeded for the key reported by the failed verification.
3. Open the **original failed run** and choose the recovery action for its target:

   | Target | Recovery action |
   | --- | --- |
   | Target preparation itself failed | **Re-run failed jobs** includes preparation, so it resolves the target before running its dependents. |
   | Main or Release | **Re-run failed jobs**. Retain the original event/release SHA. |
   | PR with the same recorded base ref, base SHA, head SHA, and merge SHA | **Re-run failed jobs**. Reuse successful shards only for that same target and configuration. |
   | PR with a changed target, or no confirmed match | Re-run the **Resolve native target and configuration** job, including when it previously succeeded. GitHub also reruns its dependent jobs: all shards and the final aggregate. Inspect the new target record. |

A PR must remain open and mergeable. Any commit, including a documentation-only
commit, changes the head SHA; an updated base or a different target branch also
invalidates the earlier target. Changes to the PR title, body, comments, or labels
do not change the tested source identity.

Failed-only recovery does not rerun successful preparation. It cannot refresh a
changed PR target. Re-running preparation keeps one target for the complete shard
set; do not combine reports from different targets. GitHub retains the original
workflow revision, dispatch ref, and inputs on this job retry. Use a new dispatch
when those need to change. See GitHub's
[job retry semantics](https://docs.github.com/en/rest/actions/workflow-runs#re-run-a-job-from-a-workflow-run).

A successful maintenance job does not substitute for SPA tests or for
exact-release-SHA verification.

CLI equivalent for the stable runtime:

```sh
gh workflow run aseprite-build.yml --ref main
# After the build succeeds, for Main/Release or an unchanged PR target:
gh run rerun <failed-run-id> --failed
```

For a changed PR target, find the preparation job's database ID and rerun it:

```sh
gh run view <failed-run-id> --json jobs \
  --jq '.jobs[] | select(.name == "Resolve native target and configuration") | .databaseId'
gh run rerun <failed-run-id> --job <prepare-job-id>
```

In the Actions UI, use the re-run control for that preparation job, rather than
the run-level **Re-run failed jobs** control. This restarts the full dependent
shard set without a separate scheduling mechanism.

A stable cache is prepared on `main`, which is readable from the other branches.
Cache visibility follows the workflow event/ref, not a later checkout of a PR
merge commit. For a provisional recipe change, first deliver the independent
builder and shared runtime action to the integration branch (normally `dev`),
then run:

```sh
gh workflow run aseprite-build.yml --ref dev
# After the build succeeds for the missing key, if the PR target is unchanged:
gh run rerun <failed-run-id> --failed
```

If the PR target changed during the build, rerun preparation as described above.

Dispatch provisional Native E2E from that same integration ref with the PR number.
Switch the consumer only after the matching cache is ready. After normal promotion,
prepare the stable cache on main. This order needs no early promotion of unrelated development work.

In the recorded #121 experiment, the PR cache token granted access to its merge
ref, dev, and main, but omitted the head branch. That run missed the exact cache
which the branch-push control restored, with matching key, version, and path. See
the [scope diagnosis](evidence/issue-107-ci-capacity.md#cache-scope-diagnosis--2026-09-28).
This establishes the recovery procedure for the observed #121 runs, not a universal
PR restriction. GitHub's cache reference also documents access to the current
feature branch. Verify visibility for the actual consumer; for this rollout,
the matching dev cache recovered #121. New manual consumers follow their dispatch
ref, so a PR checkout alone does not grant access to a dev cache. Main cannot
consume a dev or feature-branch cache.

The Actions UI needs the workflow on the default branch for normal discovery.
During #107 rollout, a registered workflow was also successfully dispatched by CLI
on a non-default branch. The temporary registration trigger is removed from the
final tree; the builder is manual-only. If an older failed run needs a different
recipe, prepare its exact key on a ref visible to that run; a newer binary is not
a substitute. GitHub documents cache scope in
[GitHub's branch restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache).

The maintenance workflow has its own concurrency group and only its build job.
It emits no SPA verification checks and must not replace them in branch protection
or release gates. CI always runs its three routine verification jobs. Maintenance never
publishes a SPA release. If a restored entry fails the native probe, inspect and
remove that exact invalid cache entry before manually rebuilding; Actions caches
are immutable.

## Platform and display requirements

Verification tier, host platform, and display capability are separate properties.
Place a platform condition on the smallest test that needs it. A passing macOS test is
macOS evidence; it is not Linux evidence. The macOS bundle and restricted-agent cases
remain macOS-specific. Issue #69 owns Linux CI and Linux real-Aseprite evidence.

Aseprite `--batch` does not start the UI. A test that produces or inspects image files
through that path is not windowed unless it actually needs a display. When a
test requires a window, declare that precondition at the test boundary and add a
shared display gate only when more than one test needs it. An optional run on a host
without display capability can skip with a visible reason. Display permission denial
must fail. A job that claims graphical coverage must fail when its required windowed
tests do not execute.

The [wizard example](../examples/wizard_cast/README.md) has two real-runtime tests:
a small component geometry proof and one complete fresh build against the checked-in
delivery. The latter independently decodes every PNG, checks hidden stored pixels,
compares the complete manifest, and reopens the delivered Aseprite source to compare
metadata, Frames, Layers, Cels, and Tags. Fetch its Git LFS assets before this local
check. The full build is marked `e2e` and `slow` and follows the opt-in policy above.
A reference macOS build takes about four minutes; one
Linux CI observation took 329.6 seconds, compared with 6.7 seconds for the small
probe. These are measurements, not time limits. Explicit double builds remain
available through the example's `verify` command, with retained local evidence.
The test does not start Godot. The example's separate Godot tests and local
windowed/package evidence are documented beside it and are not claimed by Linux CI.

The manual maintenance job builds the official source release and verifies the archive
against the version and SHA-256 authority in `.github/actions/aseprite-runtime/action.yml`. It
uses the runner's Clang 18 toolchain, Release configuration with `-O1 -DNDEBUG`,
and two build processes. This profile prioritizes compilation time for functional
verification; it does not certify Aseprite's optimized runtime performance.
The recipe enables scripting with Aseprite's `LAF_BACKEND=none`. Normal verification
checks that both `DISPLAY` and `WAYLAND_DISPLAY` are absent, builds and installs the current wheel in a separate
environment on each shard, and runs the shared real-runtime entry point. Each shard
writes its own JUnit and original-ID report. The aggregate checks the full selection
as described above, including missing/zero/all-skipped execution. The job summary
records the tested commit, trigger, executable, Aseprite
version, selected scope, display state, and exercised path. A macOS-only skip remains
visible and does not invalidate the Linux batch evidence while other E2E tests execute.

The setup action shares the cache key and probe between maintenance and verification.
The key includes Ubuntu 24.04, runner architecture, Aseprite version, source checksum,
and the content of `scripts/build_aseprite.sh`. That script owns the build recipe;
changes to workflow routing, setup messages, or tests do not invalidate the binary.
The maintenance job is the only caller that enables building and saving a missing
entry. Normal verification restores the executable and data files and repeats the
native checks. GitHub can remove entries after seven days without access or earlier
under the repository cache limit; use the manual recovery above when this happens.

The Linux real Aseprite job is also part of release verification. A release workflow
always reruns the required native suite, excluding complete example rebuilds, at the exact release commit
and does not reuse a generally green CI or weekly run. A successful macOS local run
remains separate developer evidence; it cannot replace the Linux release gate.
Windowed Aseprite behavior has no CI coverage until a
dedicated display-capable job is added with an execution-count gate.

Manual Tilemap Brightness/Contrast tests live in `tests/filter/`. They compare the
installed Operation with an independent native batch command using the same Manual
mode, Channels, Palette basis, and Canvas Selection. They cover shared Tiles across
linked and distinct Cel Images, hidden/locked references, placement flags and clipping,
the four pixel application branches, and Indexed RGB Map Alpha quantization.
Failure injection checks mixed-target rollback and editor-state restoration. Native
User Data serialization checks retain plugin metadata without interpreting its values.
These tests run in the required macOS/Linux batch scope; they do not claim windowed
editor coverage or support for AUTO/STACK mode. Grid origin evidence starts with the
reopened Source: native ASE serialization itself does not retain a live nonzero Tileset
Grid origin, including in a no-Filter control.

The [hybrid wizard example](../examples/wizard_cast_v2/README.md) uses frozen local
imagegen inputs. Its routine `e2e` probe checks the prepared raster handoff through
public Pixel Patches, native save/reopen, independent Frame placement, binary alpha,
and decoded export pixels. Its full test is also marked `slow`: one fresh build
must match the retained v2 delivery and all seven reopened native documents,
including the RGBA values of hidden stored pixels. It checks the actual v2 recipe
geometry, 32 Frames at 100 ms, four fixed phase ranges, and native gem pulse
independence. This complete rebuild runs locally on demand. Automated tests need no
imagegen service or generation credentials. macOS build
cost and Godot evidence are recorded separately in the v2 example's dogfooding
report; Linux asset CI does not establish graphical or gameplay acceptance.

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

1. Select **Tileset Mode: Manual**. Open **View → Run Command → Developer Console**.
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

## Despeckle and Convolution discovery

The #39 slice uses `tests/filter/test_unit_despeckle.py` for strict request/schema
parity and `test_integration_despeckle.py` for evidence validation before Target
Commit. `test_e2e_despeckle.py` exercises native RGB and Grayscale Channel subsets,
Indexed stored-index and supported component paths, window boundaries, tiled
edges, 1×1 RGB Map behavior, Selection, linked Cels, Background and Tilemap refusal,
and reopened output. `test_e2e_filter_state.py` injects a post-command failure to
prove rollback after native mutation and restoration of the previous editor site.

`tests/runtime/test_unit_convolution.py` checks bounded declaration scanning,
lookup paths, duplicates, defaults and incomplete input reporting.
`tests/runtime/test_e2e_convolution.py` checks discovery and retained native probes
through the installed info/schema surface. No Convolution callable capability is
inferred from a resource name or a small successful probe. The evidence record is
[issue-39-native-filters.md](evidence/issue-39-native-filters.md). Batch/native-command
parity and any local windowed comparison are reported separately there.
