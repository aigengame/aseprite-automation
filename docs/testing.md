# Test suite

For native text, `tests/paint/test_e2e_text_discovery.py` verifies the installed
Capability Gap and absence of false callability. The [issue #47 investigation](evidence/issue-47-native-text.md)
retains manual native pixel and save/reopen observations. Its text fixture is not
part of routine discovery or pytest; neither installed discovery nor CI needs to
repeat the known crash.

SPA organizes tests first by the behavior owner and then names each test file by its
verification tier. The layout does not mirror source packages or CLI Command Groups.

Tileset lifecycle #45 adds public rebind/remove E2E and an independent native oracle
for flags, Linked Cels, unchanged shared Layers, native properties, and save/reopen.
Indexed tests cover Palette validity in each actual usage Frame, including linked
Frames and different valid Palettes. Fixtures with different Palette lengths use
an alpha-bearing entry so native serialization retains the modern Palette chunk;
all-opaque legacy chunks do not encode length. A failed persistence check still
refuses publication. Plan tests cover rebind-all/remove, collection reindexing,
Step-time Cel creation receipts, one commit, malformed evidence, and later failure
with Source and an existing Target preserved.

## Ownership areas

| Directory | Behavior owner |
| --- | --- |
| `tests/application/` | Application orchestration, including compatibility checks before Operation execution. |
| `tests/ci/` | Release admission, native test execution policy, and shard evidence checks. |
| `tests/cli/` | Access Projection through the installed CLI and its in-process projections. |
| `tests/color_mode/` | Conditional Color Mode choices, native mapping/Dithering, complete Sprite and Plan conversion evidence. |
| `tests/contracts/` | Shared Published Language rules, including Failure Code registration and Operation Descriptor constraints. |
| `tests/delivery/` | Shared Artifact staging, verification/publication lifecycles, and real filesystem publication boundaries. |
| `tests/export/` | Image, GIF and PNG sequence Export contracts, independent format verification, and real Aseprite output evidence. |
| `tests/examples/` | Installed-CLI workflows, deterministic asset production, and checked-in downstream asset agreement. |
| `tests/frame/` | Frame timing, insertion, Cel copy/link intent, Tag adjustment, and native persistence. |
| `tests/filter/` | Native Filter application, Channels, Cel targets, Palette basis, state restoration, and verified publication. |
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
| `tests/script/` | Exact caller-owned Lua transport, process/file facts, bounds, and exclusion from core identities and Plans. |
| `tests/slice/` | Complete Slice Keys and coverage, exact addressing, bounded native authoring, exporter validation, and save/reopen evidence. |
| `tests/sprite/` | Sprite Domain Module contracts plus real creation, copy, flatten, bounded validation, persisted reopen, structural inspection, and Target Commit evidence. |
| `tests/tag/` | Tag stored facts, exact current addressing, native mutation, and save/reopen evidence. |
| `tests/tile/` | Tileset/Tile identity and lifecycle, exact Tilemap topology, complete Tile Region transport, native validation, Tilemap Layer create/share persistence, and explicit Tilemap Cel creation. |

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

Explicit Tilemap Cel creation (#165) lives in `tests/tile/test_e2e_cel_creation.py`.
The independent `cel_creation.lua` fixture creates a native Layer/Tileset without
SPA Layer creation, then verifies saved Cells, native Image independence, existing
links, Tile Images/Keys/properties, Palette, binding, and Grid. The matrix covers
RGB/Grayscale/Indexed (Transparent Color Index 7), first/later Frames, and both
standalone and Plan creation. Refusals and a later failing Step preserve Source
and an existing Target; a later successful Step may change the initial links.
Contract tests cover installed schemas, geometry bounds, conditional runtime
capability, and contradictory creation evidence without launching Aseprite,
including Tileset ordinals and Grid facts that disagree with complete Sprite
inspection. Positive controls include a valid second Tileset.
These are batch E2E tests: local macOS results do not establish Linux verification.

Tile lifecycle #43 uses `test_e2e_lifecycle.py` with public CLI requests and an
independent native oracle. It checks opaque plugin data, Linked Cels across shared
and nested Layers, explicit removal replacements above/below the removed index,
Empty versus flagged index 0, orphan reorder cleanup, all three Image Color Modes,
Frame-varying Palettes, and Source/Target preservation on refusal. The same tests
belong to `e2e and not slow` on macOS and Linux; no display is required. Fast tests
check schema and preflight behavior. Boundary fixtures cover inline pixels,
before/after Tile counts, and referenced Cell totals across shared Layers and
Linked Cels, including unchanged Empty Cells. They also verify explicit refusal
of transparent hidden RGB/Gray and the accepted transparent-zero case. See
[native mechanism evidence](evidence/issue-43-tiles.md).

External raster import #46 checks 8-bit PNG metadata independently of native
loading, then compares full RGBA and stored indexes through real insertion and
save/reopen. Fixtures cover used-index Palette equality at the selected Frame,
mask collisions, partial alpha and transparent hidden RGB, None/sRGB/supported ICC,
empty-slot eligibility, signed Cel positions, and independent Images beside linked
Cels. Failure cases preserve inputs and any previous Target, discard staging, and
refuse inconsistent native evidence or output aliases of the raster. These tests
use the existing local macOS and Linux `--batch --script` lanes without a display;
they do not exercise the editor UI. Run `pytest tests/import` with the same runtime
configuration as other native owners.

## Animation export

`tests/export/test_e2e_animation_export.py` exercises the public GIF and PNG sequence
Operations independently. Native fixtures check explicit and repeated Frames, one
Tag direction traversal without repeat expansion, full Canvas, occurrence naming,
PNG Color Mode and alpha, per-Frame Indexed Palettes with Linked Cels, supported
profiles, GIF duration truncation, infinite looping, and allowed native color loss.
The accepted representation matrix is documented in the [usage guide](usage.md#export).
Unknown profiles, unsupported representation combinations and GIF Frames below
10 ms are refused before publication. ICC-to-sRGB GIF conversion remains conditional
on the actual runtime's separately observed Color Profile capability; macOS evidence
does not remove the Linux conversion Capability Gap.

The native `opaque red → fully transparent → opaque green` GIF regression retains
a bounded macOS arm64 Aseprite 1.3.18.5-dev / API 41 observation: the blank occurrence
can contain residual opaque pixels. Independent per-Frame alpha verification rejects
that staged output and preserves any existing final destination. This verifies refusal
for the observed encoding path, not a limitation across all releases or a repaired GIF.
Future accepted requirements and reliable native evidence can extend this boundary.

`test_unit_animation_decoders.py` separately verifies encoded PNG samples, Palette,
profile and transparency facts and GIF blocks, color tables, disposal, timing and
loop observations, including malformed bytes. Real filesystem tests in
`tests/delivery/test_integration_artifact_set.py` check complete-set preflight, exact
regular-file staging, digest tampering, Source alias refusal and allocation cleanup.
Failure injection after one replacement checks every ordered publication state;
an exception after a final write reports the current path as `indeterminate`.
Published files are retained and no successful Artifact set is returned.

PNG ICC tests cover the bundled linear-sRGB and CC0 Display P3 identities in RGB and Indexed modes. Aseprite's
`none` backend leaves the loaded ICC display name empty, which libpng rejects as an
empty iCCP keyword. Export assigns a nonempty label to the private PNG container's
profile copy. This changes neither the Source nor the ICC payload; independent
decoding still requires exact ICC bytes. The converter capability is unrelated to
this encoding label.

Optional caller-supplied Apple P3 checks require `SPA_TEST_APPLE_P3_ICC` to point to
the exact previously admitted local file. They skip when it is unset; tests do not
search the host or download that file. Normal CI needs only the bundled CC0 reference.
The optional checks exercise the caller's original bytes through native conversion,
live Plans, Preparation, Import, and PNG export, including refusal between the distinct P3 identities. A successful
CC0 probe alone does not establish Apple conversion on a new runtime. See
[#194 evidence](evidence/issue-194-redistributable-profile.md).

`tests/export/test_e2e_wizard_animation_export.py` reuses the retained v2 Sources and
delivery PNGs. It exports all 193 retained outputs: 32 Frames each for Scene,
Background, Wizard, Gem, Burst and Projectile, plus the single Target Frame.
Ten additional Gem and Projectile occurrences check repeated and nonmonotonic
playback around blank Frames, scale pulses and emission. The tests independently
compare all 203 PNGs, filenames, playback, profiles and Source bytes. A separate
five-occurrence Gem GIF checks binary alpha, duration, infinite looping and exact
visible colors on that finite fixture. These are bounded `e2e` batch tests in
`e2e and not slow`; they reuse the saved Sources without rebuilding the authoring
recipe, running Godot, or claiming visual/play acceptance. Fetch the retained Git
LFS assets first.
Run `pytest tests/export tests/delivery` with the normal `SPA_TEST_ASEPRITE`
configuration. Results apply to the actual tested runtime and platform.

## Verification tiers

Frozen raster preparation #103 has fast public-dispatch tests for malformed input,
geometry/Palette rules, reproduction mismatch, contradictory native/PNG evidence,
alias safety, and publication failure cleanup. Installed-CLI native cases use an
independent small raster and the existing frozen wizard input. They cover all four
rounding policies, threshold boundaries, empty explicit crops, outside anchors,
exact PLTE/tRNS with transparent indices 0/7/255, complete RGBA/Indexed parity,
and reproduction. The wider-gamut ICC counterexample checks conversion before
mapping; runtimes without native conversion must report `runtime_incompatible`.
These are bounded `e2e` batch tests, not windowed UI or complete example rebuilds.
Run `pytest tests/preparation` with the normal `SPA_TEST_ASEPRITE` configuration;
local macOS evidence and unexecuted Linux coverage are distinguished in
[the preparation report](evidence/issue-103-raster-preparation.md).

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

The [installed distribution record](evidence/issue-54-installed-distributions.md)
records the tested macOS profile, the isolated-wheel replay, and the remaining
Linux evidence for the Release-only runner. Its earlier Linux build/cache profile
is historical. `scripts/verify_installed_cli.py` rejects
editable/source-tree imports and checks all packaged Kernel resources. Both the
distribution smoke action and the Linux native action reuse that verifier. The
native wheel cases cover `info`, Plan creation/painting/inspection, PNG export
and a typed failure; they run consumer calls outside the checkout.

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
| Routine PR update, main push, or manual CI | None; source, fast-test and distribution checks only. |
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
responses. It covers stale PR targets, merge-parent mismatches, main-only routing,
API failures, Release PR head convergence and metadata checks. These tests do not
establish runner-group enforcement, token permissions or Linux native execution.

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


## Tileset atlas and normalized map export

`tests/export/test_e2e_tileset_export.py` exercises `spa export tileset` with a real
Aseprite process. It verifies complete Tileset coverage, unused keyed Tiles, Tile 0,
explicit-column layout and padding, Cel-local regions and placement flags, exact RGB
and Grayscale channels, and Indexed Frame-based Palette selection. The Indexed fixture
has two Palette Changes, a nonzero Transparent Color Index, duplicate and unused
entries, and partial alpha. A 257-color RGB Tile guards against implicit quantization.
The accepted Profile matrix includes None and sRGB in all three modes, and the fixed
linear-sRGB/Display P3 ICC files in RGB/Indexed. Grayscale with these ICC files and
other Profiles are refused before publication. Tests independently decode PNG and JSON
and check Source bytes after execution.

Fast integration tests corrupt staged outputs and inject publication failures through
the Kernel/File boundaries. They verify that missing, malformed or inconsistent pairs
never publish, and that failure after the image publishes reports both path states
without rollback or cleanup. The native suite uses batch scripting and requires no
windowed UI. Evidence applies to the runtime on which it was executed; these tests do
not establish a separate Aseprite version matrix.

```sh
uv run --frozen --group test pytest tests/export -m "not e2e"
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/export/test_e2e_tileset_export.py -x -vv --tb=short -rs
```


## Caller-owned Lua

Issue #51 tests the separate installed `spa script run` path. Contract tests cover
all Execution Kind / Determinism pairings in both model validation and JSON Schema.
Installed discovery reports `script-run` / `caller-defined`, while request and Plan
tests prevent caller source or printed JSON from becoming an Ordinary Core Operation.

Controlled process tests cover timeout (including early closure of both output
streams), the 65,536-byte per-stream guard, nonzero exit, exact UTF-8 materialization,
and typed failures. Real batch E2E covers native Lua and syntax errors, unchanged
BOM rejection, file bytes and CRLF preservation, script-relative `require`, explicit
parameters, binary-to-text replacement, and declared file facts. These are batch
tests, with no windowed UI requirement or claim. Current macOS and Linux profiles
run them through the existing `e2e and not slow` selection; one profile's evidence
does not establish the other.

```sh
uv run --frozen --group test pytest tests/script tests/contracts/test_unit_determinism.py -m "not e2e"
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/script -m e2e -x -vv --tb=short
```

## MCP Access Projection

`tests/mcp/` uses real stdio clients pinned separately to `2026-07-28` and the
SDK legacy `2025-11-25` path. Controlled CLI subprocesses test wire projection,
diagnostics and cleanup. The native tests compare every tool schema with the
installed Manifest, then create, inspect, validate and export through real
Aseprite. They decode ImageContent and compare bytes, digest and pixels; ordinary
fast tests cover removed/changed Artifact files and distinguish projection failure
from a completed Operation.

```sh
SPA_TEST_ASEPRITE=/absolute/path/to/aseprite \
  uv run --frozen --group test pytest tests/mcp -q
```

The test dependency group includes the optional MCP SDK. Routine CI still runs
`not e2e`; the installed native paths join the existing `e2e and not slow` selection.
No new workflow, example rebuild or automatic native trigger is added.
