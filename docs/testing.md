# Test suite

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

## Ownership areas

| Directory | Behavior owner |
| --- | --- |
| `tests/application/` | Application orchestration, including compatibility checks before Operation execution. |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration and Operation Descriptor constraints. |
| `tests/export/` | Image Export contract, PNG Artifact verification and publication, and real Aseprite output evidence. |
| `tests/examples/` | Installed-CLI workflows, deterministic asset production, and checked-in downstream asset agreement. |
| `tests/frame/` | Frame timing, insertion, Cel copy/link intent, Tag adjustment, and native persistence. |
| `tests/layer/` | Layer hierarchy, exact addressing, and native addition evidence. |
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

The initial evidence profiles use local macOS Aseprite 1.3.18.5-dev and the pinned
Linux CI Aseprite 1.3.18.5 source release. Both expose `_VERSION == "Lua 5.4"` and
`app.apiVersion == 41`; the macOS build's vendored Lua 5.4.6 records source provenance,
not a patch-level compatibility rule. The E2E assertion pins this evidence family while
the runtime compatibility decision continues to use the Descriptor's observed language
and API requirements.

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

`.github/workflows/ci.yml` runs on every pull request and every push to `main`. The
Release workflow also dispatches it explicitly for the Release PR branch because
GitHub does not emit a second workflow event for a pull request updated with
`GITHUB_TOKEN`. All jobs use Python 3.13, uv 0.11.19, and the committed `uv.lock` with
`--frozen`.

| Job | Required evidence |
| --- | --- |
| Source quality | Ruff lint and formatting, Pyright for production source, and Luacheck plus StyLua for all tracked Lua. |
| Fast tests | Unit and integration tests selected with `-m "not e2e"`. |
| Build and smoke test distributions | One sdist and wheel, valid package metadata, and a successful `spa version` from a wheel-only environment populated from locked runtime dependencies. |
| Linux real Aseprite E2E | The project CLI and a wheel-installed CLI drive the pinned real Aseprite `--batch --script` path. A wheel-only negative case reaches the packaged Sprite creation handler and proves that no Target Commit occurs after rejection; a wheel-only Export case verifies a PNG Artifact. The job records JUnit evidence. |

A failure in any job fails CI. Configure these four named jobs as required checks on
`main` when repository branch protection is enabled.

### Complete example rebuilds

The Linux E2E job is required for every verification event. These events use the
same native suite; excluding complete example rebuilds does not skip the required
CI check. Manual `task=build-aseprite` is a separate maintenance operation:

| Trigger | Real-runtime selection |
| --- | --- |
| Every PR or push to `main`, including example and CI changes | `e2e and not slow`: all routine E2E cases, including the small wizard probes. |
| Nightly on `main` | `e2e and not slow` at the scheduled main SHA. |
| Manual **CI → Run workflow**, `task=verify` | `e2e and not slow` at the selected ref. |
| Release verification | `e2e and not slow` at the exact release SHA before publication. |

The shared `.github/actions/run-linux-aseprite-e2e/action.yml` owns this selection.
It retains all other native assertions, both small wizard probes, and the hybrid
hidden-pixel comparison regression. The owner removed both complete example
rebuilds from automated gates on 2026-09-28 after reviewing their measured cost.
Nightly/manual full verification covers the required tool suite; it does not
regenerate the example deliveries. To check complete asset reproducibility after
an example change, use the example build/verify commands or run locally:

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest -m "e2e and slow" -rs
```

These checks still compare full deliveries and hidden native pixels. Their results
are separate, explicit evidence; automated CI no longer claims that coverage.

The nightly schedule is daily at 19:23 UTC (03:23 Asia/Shanghai). GitHub runs it
from the default branch, `main`; the job also checks that ref explicitly. `dev`
is a temporary integration branch and has no nightly target. The schedule becomes
active after this workflow reaches `main`. Pushes and manual runs do not cancel a
nightly run. Its summary records the actual checked-out SHA and selected test scope.
Scheduled runs can be delayed; their result never replaces exact-SHA
release verification.

### Verification time limits

GitHub's native job timeouts enforce **20 minutes for routine PR/push native
verification**, **40 minutes for nightly/manual native verification**, and
**40 minutes for Release verification**. All work inside each job counts, including
checkout, runtime setup, tests, package checks where present, and uploads. There
is no compilation deduction or second clock. Source quality, fast-test, and package
CI jobs retain their smaller 10-minute limits and run in parallel.

These are running-job limits, not queue-time or whole-pipeline latency promises.
Release has separate draft and publication jobs; its 40-minute limit applies to
`Verify exact release commit`. An overrun fails verification and prevents publication.
The [issue #107 evidence](evidence/issue-107-ci-capacity.md) records the measurements
and superseded experiments.

### Restore the Aseprite runtime

Normal PR/push CI, nightly, manual `task=verify` (the default), and Release only
restore an exact Aseprite cache entry. A miss fails before native dependency
installation or compilation and identifies the required key. It does not skip the
native gate or report success. A restored binary must still pass the executable,
resource, version, and real `--batch --script` checks before SPA's E2E suite runs.

To recover:

1. Open **Actions → CI → Run workflow**, select the recipe branch and
   `task=build-aseprite`. Use **main for the stable runtime**. This selection runs
   only **Build Aseprite (manual maintenance)** with its own 40-minute native job
   timeout. It validates the pinned source checksum, builds if the exact cache is
   missing, checks the real batch/script path, and saves the verified tree.
2. Confirm that the job succeeded for the key reported by the failed verification.
3. Open the **original failed run** and choose **Re-run failed jobs**. This retains
   its original SHA/ref. A successful maintenance job does not substitute for SPA
   tests or for exact-release-SHA verification.

CLI equivalent for the stable runtime:

```sh
gh workflow run ci.yml --ref main -f task=build-aseprite
# After the build succeeds:
gh run rerun <failed-run-id> --failed
```

The existing CI workflow is already registered on main. Before this change is
promoted, invoke that same workflow with `--ref <implementation-branch>` and
`-f task=build-aseprite` to verify the provisional recipe. The main UI receives the
new selector after promotion; no separate workflow registration is required.

A main cache is available to other branches. A PR can also read its head/base
branch caches, but main cannot consume a feature/dev cache. Build recipe changes
must be prepared on the corresponding branch for provisional verification, then
on main after promotion. Do not infer main readiness from a branch build. If an
older failed run needs a different recipe, prepare its exact key on a ref visible
to that run; a newer binary is not a substitute. Cache access follows
[GitHub's branch restrictions](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache).

The maintenance selection has separate concurrency and skipped-check names, so it
does not cancel a manual verification or emit skipped successes under the normal
verification check names. It never publishes a SPA release. If a restored entry
fails the native probe, inspect and remove that exact invalid cache entry before
manually rebuilding; Actions caches are immutable.

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
against the version and SHA-256 authority in `.github/actions/setup-linux-aseprite/action.yml`. It
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
and does not reuse a generally green CI or nightly run. A successful macOS local run
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
