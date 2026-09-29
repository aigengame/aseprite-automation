# Test suite

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

## Ownership areas

| Directory | Behavior owner |
| --- | --- |
| `tests/application/` | Application orchestration, including compatibility checks before Operation execution. |
| `tests/ci/` | CI target selection and pre-merge evidence checks. |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration and Operation Descriptor constraints. |
| `tests/export/` | Image Export contract, PNG Artifact verification and publication, and real Aseprite output evidence. |
| `tests/examples/` | Installed-CLI workflows, deterministic asset production, and checked-in downstream asset agreement. |
| `tests/frame/` | Frame timing, insertion, Cel copy/link intent, Tag adjustment, and native persistence. |
| `tests/layer/` | Layer hierarchy, exact addressing, and native addition evidence. |
| `tests/motion/` | Bounded Cel curve sampling, complete preflight, and persisted pixel/property preservation. |
| `tests/paint/` | Paint Domain Module contract, bounded mutation evidence, and native Pixel Patch behavior. |
| `tests/palette/` | Shared Effective Palette resolution over native Frame-based Palette Changes. |
| `tests/plan/` | Static Plan preflight, single-Sprite Step composition, and commit gates. |
| `tests/release/` | Release metadata and publication gates. |
| `tests/runtime/` | Aseprite Runtime Integration, including discovery, launch, private Kernel transport, and real-runtime evidence. |
| `tests/sprite/` | Sprite Domain Module contracts plus real creation, copy, flatten, bounded validation, persisted reopen, structural inspection, and Target Commit evidence. |
| `tests/tag/` | Tag stored facts, exact current addressing, native mutation, and save/reopen evidence. |

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
  uv run --frozen --group test pytest tests/paint -q
```

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
and combines it with public Slice user data. The private metadata and texture remain in
the invocation workspace.
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

Run the routine real-runtime tests, including the small wizard probe, with:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test pytest -m "e2e and not slow" -rs
```

Run the full real-runtime tier, including complete example rebuilds, with:

```sh
SPA_TEST_ASEPRITE=/path/to/aseprite \
  uv run --frozen --group test pytest -m e2e -rs
```

Use `-rs` so platform and environment skips remain visible. Use collection output when
moving tests to confirm that parametrized cases were preserved:

```sh
uv run --frozen --group test pytest --collect-only -q
```

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
weekly main regression. It has one unconditional **Linux real Aseprite E2E** job.
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
state changed. The summary and artifact retain the target and JUnit evidence.
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
run in the PR. A later head/base update invalidates this evidence; dispatch a new
run. Do not enable delayed auto-merge with stale native evidence. An unrun,
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

The shared `.github/actions/run-linux-aseprite-e2e/action.yml` owns the native
selection. It retains the project and wheel-installed CLI paths, real
`--batch --script` probe, both small wizard probes, hidden-pixel regressions and
all other native assertions. The owner removed both complete example rebuilds
from automated gates on 2026-09-28 after reviewing their measured cost. Full native
verification means the required tool suite, without regenerating example deliveries.
For complete asset reproducibility after an example change, use its build/verify
commands or run locally:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest -m "e2e and slow" -rs
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
every diagnostic push or rerun all jobs when only one failed. macOS results remain
macOS evidence. `act` can help with shell/container checks, but does not reproduce
all GitHub permissions, concurrency or timeout behavior; see its
[unsupported features](https://nektosact.com/not_supported.html).

### Verification time limits

The owner limits remain **20 minutes for routine CI**, **40 minutes for full
manual/periodic verification**, and **40 minutes for Release verification**.
GitHub's native job timeouts enforce them: the three parallel routine jobs retain
their smaller 10-minute limits, Native E2E has 40 minutes, and Release's
`Verify exact release commit` has 40 minutes. All job steps count, including
checkout, setup, tests, package checks where present and uploads. There is no
compilation deduction or second clock.

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
3. Open the **original failed run** and choose **Re-run failed jobs**. Main and
   Release verification retain their original event/release SHA. PR-mode Native
   E2E resolves the current PR again; inspect its new base/head/merge record.
   A successful maintenance job does not substitute for SPA tests or for
   exact-release-SHA verification.

CLI equivalent for the stable runtime:

```sh
gh workflow run aseprite-build.yml --ref main
# After the build succeeds:
gh run rerun <failed-run-id> --failed
```

A stable cache is prepared on `main`, which is readable from the other branches.
Cache visibility follows the workflow event/ref, not a later checkout of a PR
merge commit. For a provisional recipe change, first deliver the independent
builder and shared runtime action to the integration branch (normally `dev`),
then run:

```sh
gh workflow run aseprite-build.yml --ref dev
# After the build succeeds for the missing key:
gh run rerun <failed-run-id> --failed
```

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
through that path is not windowed unless it actually needs a display. When a future
test does require a window, declare that precondition at the test boundary and add a
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
environment, and runs the required real-runtime tier with two pytest-xdist worker
processes. Test workspaces and each Aseprite user folder remain isolated; the
controller writes one JUnit report. The JUnit audit
fails when the report is missing, contains zero tests, or all selected tests were
skipped. The job summary records the tested commit, trigger, executable, Aseprite
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
