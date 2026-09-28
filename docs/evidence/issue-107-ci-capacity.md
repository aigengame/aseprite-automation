# Linux CI capacity — issue #107

## Current acceptance

The latest owner decision on 2026-09-28 replaces the measured-build deduction
experiment. Verification now uses native job timeouts: PR/push 20 minutes,
nightly/manual verification 40 minutes, and Release verification 40 minutes.
Aseprite cache misses fail verification without compilation. Maintenance runs in
the independent, manual-only `aseprite-build.yml` with a 40-minute job timeout;
its success is followed by a rerun of the original failed verification. Stable
binaries are prepared on main. Provisional recovery for the observed #121 runs
uses dev with the same recipe; their tokens did not include the head-branch scope.

The owner subsequently approved separating the workflow after reviewing the cost
of sharing CI's entry. The CI task selector, conditional check names, maintenance
job, and task-specific concurrency are removed. Both complete wizard rebuilds
remain local opt-in checks. The exact-release-SHA gate and retained native suite
stay required. The investigation below corrects the earlier assumption that
promotion to main was required to diagnose or test the independent entry. The
PR recovery needs a matching cache on a readable ref. Bootstrap
[PR #124](https://github.com/aigengame/aseprite-automation/pull/124) delivered the
builder to dev at `637885e015fa30b2f413fc383c0f147eed69b34c`; #121 integrates that
commit before switching the CI consumer. The current build and rerun results are
recorded on [PR #121](https://github.com/aigengame/aseprite-automation/pull/121).

## Cache scope diagnosis — 2026-09-28

Temporary experiment `065d8c378a829bd5713478e61eace9d642e37ffc` inspected only the
scope and permission fields of the Actions cache runtime claim. It did not print
the token or other credential claims. Both runs used the same pinned cache action,
key, cache version, and installation path:

| Event | Readable cache refs reported by the runtime | Result |
| --- | --- | --- |
| [PR](https://github.com/aigengame/aseprite-automation/actions/runs/36403984682/job/108868185367) | `refs/pull/121/merge` (permission 3), `refs/heads/dev` (1), `refs/heads/main` (1) | Miss; failed in 8 seconds |
| [Push](https://github.com/aigengame/aseprite-automation/actions/runs/36403979366/job/108868168791) | `refs/heads/codex/issue-107-ci-capacity` (3), `refs/heads/main` (1) | Exact hit; succeeded in 14 seconds |

**Observed cause for #121:** the saved binary belongs to the head branch, which is
absent from this PR run's reported cache permissions. Its token grants dev/main
access; prepare the exact key on dev and verify recovery by rerunning the original
failed job. Repeating the recorded scope and head-cache state cannot recover it.
These observations do not establish a universal GitHub PR rule: the current
[cache reference](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching#restrictions-for-accessing-a-cache)
also documents access to the current feature branch. The discrepancy does not
change this run's observed scopes or justify a cache transport workaround.

A separate dispatch experiment removed all automatic triggers after registration
and successfully ran a
[manual-only workflow on the feature branch](https://github.com/aigengame/aseprite-automation/actions/runs/36404440635/job/108869679034)
at `a70a8e7`. The file was absent from main. This disproves the earlier claim that
main promotion was necessary for every dispatch. Dispatching directly to
`refs/pull/121/merge` was rejected with HTTP 422 (`No ref found`), so it is not a
manual cache preparation path. The temporary experiment files and registration
triggers are removed from the final tree.

The final independent
[Build Aseprite workflow](https://github.com/aigengame/aseprite-automation/actions/runs/36405612194/job/108873489696)
also succeeded at `912aa44819a5f8aedec3371ba7da4ae182add6fa` via
`workflow_dispatch` in **15 seconds** (09:46:26–09:46:41 UTC). It restored the exact
feature-branch cache, skipped compilation, and passed the resource/version and real
batch/script checks. Its final file has only the manual trigger. This verifies the
independent entry before main promotion; it does not establish dev cache save or PR
recovery. The same producer files are present in the bootstrap PR.

Rollout: additive [PR #124](https://github.com/aigengame/aseprite-automation/pull/124)
delivered the independent manual builder, shared runtime action, and unchanged
build recipe to dev while retaining its legacy CI. The next steps are Build
Aseprite on dev and a rerun of the original #121 verification. #121 switches to the
shared action and removes the legacy setup. The final tree has one runtime owner;
this is a delivery order, not a second permanent build mechanism. PR #121 records
the dev build, original-run recovery and current-head verification evidence.

## Shared-action recovery validation — 2026-09-28

The replacement implementation is `aa588fc557121e0c5d17ebf163a7f0bd0b904f65`.
The [initial PR verification](https://github.com/aigengame/aseprite-automation/actions/runs/36399147774/job/108852606621)
used actual merge checkout `f012a5ca2177a5b1a8067e52a6c7b53d4108064f`.
The native job failed as required in **22 seconds**, 08:44:21–08:44:43 UTC.
The cache lookup took 0.443 seconds and returned a miss; the next 0.023-second
step reported the required binary/key and manual-build/retry instructions.
Native OS dependency installation, compilation, cache save, and native E2E were
skipped after that failure. There is no native JUnit report for this expected
refusal. The independent source, fast-test, and distribution jobs passed.

Before the workflow split, the existing manual entry accepted
`task=build-aseprite` on the implementation branch even though main did not yet
contain the new input:
[manual preparation](https://github.com/aigengame/aseprite-automation/actions/runs/36399311924).
Only the maintenance job runs; the normal verification check names are not emitted
as skipped successes. This temporary entry has now been removed from CI. The build
script, cache identity, and native probe remain shared and unchanged by that split.
The job succeeded in **23m 26s** (08:46:36–09:10:02 UTC). Source SHA-256 validation,
the executable/resource/version checks, and the real batch/script probe passed
before cache save. The build had two allocated CPUs (AMD EPYC 7763 host); the
compiler command itself took 21m 42.887s. The reported runtime is Aseprite
`1.3.18.5-dev`. This run cannot validate the new workflow's dispatch entry.

Saved cache `8204157704` has:

- Ref: `refs/heads/codex/issue-107-ci-capacity`.
- Key: `spa-aseprite-cli-ubuntu-24.04-X64-1.3.18.5-04b0a84617efb3107d380c352ebb0af9eb2633ff4c1a8bfcb671d2a437247d5d-01760cb1bf26fe447f65a9c85730607846c261c3f004a36aa32e0d84370d52ee`.
- Cache version: `f9065ecba5600982730587a8798547f1be7afbe92c18c9d791d13e8d4b161b96`.
- Path: `/home/runner/work/_temp/spa-aseprite/1.3.18.5`.

**PR recovery did not pass.** The
[original rerun, attempt 2](https://github.com/aigengame/aseprite-automation/actions/runs/36399147774/job/108861274785)
failed in 15 seconds on another miss. The
[new split-workflow PR run](https://github.com/aigengame/aseprite-automation/actions/runs/36401859256/job/108861348222)
at `3fbd19d92c4911537974c3805ae96442dc0d432d` also missed; its other three CI jobs
passed. A single
[debug rerun, attempt 3](https://github.com/aigengame/aseprite-automation/actions/runs/36399147774/job/108862078332)
explicitly reported a miss for the saved key **and cache version**. The paths match,
and this is a same-repository PR. The original reruns checked out the original
merge SHA `f012a5ca2177a5b1a8067e52a6c7b53d4108064f`.

At this checkpoint, these observations disproved the assumed head-branch recovery
but did not yet establish its cause. The later scope diagnosis above does. Native
installation, compilation, and E2E were not executed after those misses; no passing
PR native evidence is claimed. Recovery requires the exact cache on dev or main.

The separate
[manual Release verification](https://github.com/aigengame/aseprite-automation/actions/runs/36401855052/job/108861340361)
at exact SHA `3fbd19d92c4911537974c3805ae96442dc0d432d` succeeded in **8m 25s**
(09:11:11–09:19:36 UTC). It restored the same feature-branch cache, skipped
compilation, and passed the native probe. Source quality, fast tests (275 passed,
four existing skips), release metadata, package checks, and evidence uploads passed.
The native action took 410 seconds; pytest recorded 399.848 seconds and **507 passes,
three existing platform skips**. All 510 native case identities and outcomes match
the preceding retained-suite report from run `36394533499`; there are no added or
removed cases. Small wizard probes and hidden-pixel checks remain; neither complete
wizard rebuild ran. Draft, publish, and release-maintenance jobs were skipped on
this manual event, so no release was created or published.

This verifies consumption on the same branch within the native 40-minute Release
limit. It does not replace the failed PR recovery or the new manual entry's first
main run. Sol Standards and architecture reviews found no blocker at `3fbd19d`.
The Spec review correctly retained the recovery acceptance gap at that checkpoint.
The later scope experiment establishes the cause and a dev-based recovery order;
a passing PR native gate still requires execution after base-branch preparation.

## Superseded measured-build deduction experiment

The next section records the earlier decision and experiment, not current policy.
The owner rejected its second clock, custom timeout handling, and 60/80-minute job
ceilings. That helper and its dedicated tests have been removed. The current
workflow and recovery contract are in `docs/testing.md`.

### Historical budget boundary — 2026-09-28 (superseded)

Recent non-experiment observations found 18 native cache lookups and 18 hits among
20 CI runs; two runs were waiting for workflow approval. The main cache created
on September 21 was still accessed on September 28. Repeated setup-action edits in
the experiments below changed the key and do not represent ordinary cold-miss
frequency. The owner therefore excluded cold build time rather than changing
runtime supply or runner capacity.

`scripts/ci_budget.py` accounts for elapsed time minus the measured cache-miss
source/configure/build step. The result must fit 20 minutes for PR/push CI and
40 minutes for nightly/manual CI or Release. Warm-cache runs receive no exemption.
Dependencies, cache restore, native probes, tests, quality, packaging, and evidence
uploads remain charged. Native tests and the Release source/fast-test/metadata
commands use the remaining budget; a final check after uploads enforces the total.
The cold build has a separate 40-minute safety limit. Outer job ceilings are 60/80
minutes solely to accommodate both allowances. GitHub-managed steps and post-job
cleanup have the timing limitations documented in `docs/testing.md`.

The earlier `a76c88b` Release result provides an accounting cross-check:
1,895 seconds total minus 1,370.334 seconds of cold build is approximately
525 seconds (8m 45s) charged under the revised policy. This is a calculation from
the recorded job, not an execution of the new accounting helper. New workflow
evidence is required before accepting that helper.

## Initial measurement method

The initial observations measured the existing Linux jobs without reducing native-pixel checks or excluding
either wizard rebuild. Use the same source and test revision for the cold and warm
observations: `e6f50811ead6f366408d8f20f41723227cad5db8`.

- Cold observation: manually dispatch the existing Release workflow. Its manual
  path runs verification only, including quality, fast tests, full native E2E,
  release metadata, distributions, wheel smoke checks, and evidence uploads.
- Warm observation: after the cold run saves the verified native executable,
  dispatch the existing CI workflow on the same branch and commit. Its full E2E
  job can restore that branch's cache. Hold the remote branch at that commit until
  dispatch; verify both runs' actual SHAs and cache outcomes from GitHub evidence.
- Cache identity changes because the setup action now records its runner/cache
  facts. The version, source checksum, compiler options, two-process build, cache
  scope rules, native setup checks, and test assertions are unchanged. No cache is
  deleted, and no forced-miss switch or separate benchmark workflow is added.
- GitHub job timestamps measure the whole job. Composite-action log timestamps and
  duration records separate setup, compilation, test execution, and verification.
  JUnit records identify the executed and skipped cases and both wizard rebuilds.
  These are individual observations, not a percentile or a speedup guarantee.

## Previous capacity evidence

The [main nightly run](https://github.com/aigengame/aseprite-automation/actions/runs/36354885280)
at `e30aee180145c85dd3579789528c560c77df0df4` on 2026-09-27 used the warm
Aseprite cache. Its full E2E job took **2,325 seconds (38m 45s)** against a
2,400-second budget, leaving **75 seconds**. Pytest took 2,283.51 seconds:
278 passed, three platform-specific skips, and 195 deselected non-E2E tests.
The v1 and v2 complete rebuild cases took 372.449 and 1,617.798 seconds.
This older revision supplies risk evidence, not the new fixed-revision comparison.

## Initial full-suite observations

Both fixed-revision observations passed on 2026-09-28:

- [Cold full Release verification](https://github.com/aigengame/aseprite-automation/actions/runs/36371009814/job/108767184550):
  02:45:06–03:47:34 UTC; native cache miss; verified build saved at 03:04:09 UTC.
- [Warm full CI](https://github.com/aigengame/aseprite-automation/actions/runs/36372268003/job/108770893549):
  03:04:47–03:30:33 UTC; exact native cache hit; compilation skipped.

Both logs confirm checkout `e6f50811ead6f366408d8f20f41723227cad5db8`. Both
JUnit reports contain the same 512 case identities and outcomes: **509 passed,
three platform-specific skips**, and 276 non-E2E cases deselected. The two complete
wizard rebuilds passed in each run.

| Measured phase, seconds | Cold Release | Warm full CI |
| --- | ---: | ---: |
| Python setup inside the native action | 0.803 | 7.906 |
| Native OS dependencies | 14.863 | 23.328 |
| Native cache lookup/restore | 0.298 | 1.557 |
| Source download, configure, and native build | 1,033.127 | 0, skipped |
| Native batch/script cache probe | 0.166 | 0.098 |
| Verified native cache save | 0.761 | 0, skipped |
| Wheel build/install for native CLI tests | 0.386 | 0.515 |
| Pytest, including native pixel and save/reopen assertions | 2,596.79 | 1,497.28 |
| Of pytest: v1 complete rebuild | 408.177 | 250.360 |
| Of pytest: v2 complete rebuild | 1,657.979 | 904.337 |
| After pytest summary through JUnit execution audit | 0.133 | 0.150 |
| Whole native action, including setup and evidence summary | 3,648 | 1,532 |
| JUnit artifact upload | 1 | 2 |
| Whole job, including checkout and cleanup | **3,748 (62m 28s)** | **1,546 (25m 46s)** |

Composite duration records supply setup/build timings; pytest and JUnit supply
test timings. The post-pytest interval includes interpreter exit/startup and the
JUnit audit, not just the audit function. Native pixel and saved-state verification
remain inside the tests and are not counted again as a separate phase. Whole-stage
and upload durations use GitHub's second-resolution step timestamps; subtotal rows
overlap and must not be added together.

Release verification separately passed initial Python/Lua setup (5 and 1 seconds),
source quality (10 seconds), fast tests (68 seconds; 272 passed, four platform
skips), release metadata (less than one second), distribution build and installed
wheel/resource smoke checks (2 seconds), and distribution upload (1 second).
The whole Release job took 100 seconds more than its native action. Manual
verification skipped draft creation, publication, and Release PR maintenance.

An additional [routine PR job](https://github.com/aigengame/aseprite-automation/actions/runs/36372352881/job/108771130318)
tested PR head `1a932e4098e55a4ca6097ff7795068bb88092c9f` through GitHub's actual
merge checkout `99d27184c6f7b1fe34b6d6b41629eafb2ea4ecaa`. It had a cold PR-scoped
native cache, compiled in 1,037.850 seconds, and passed 507 tests with three
platform skips and 281 deselected cases. Its whole job took 1,636 seconds
(27m 16s), leaving 764 seconds (12m 44s) of the then-configured 40-minute budget.
Both complete wizard rebuilds were deselected, as required for PR events.
The additional head changes only release maintenance, its three fast regression
tests, and release documentation; it does not change the native workload.

The corresponding [warm routine PR job](https://github.com/aigengame/aseprite-automation/actions/runs/36375395881/job/108780079876)
ran at head `2725dd49ab44c9403cccc1f06bbc8376e4910e99`, whose additional changes
were documentation only. It used the same native workload and cache key, recorded
an exact cache hit, and skipped compilation. The job took **564 seconds (9m 24s)**;
pytest took 524.94 seconds and again reported 507 passed, three platform skips,
and 281 deselected cases. This same-scope pair saved 17m 52s with a warm cache.
It confirms cache reuse; the different-scope 25m 46s and 27m 16s observations do
not measure cache speedup.

The initial cold Release, warm full CI, and cold routine CI jobs used Linux X64, Ubuntu 24.04 image
`20260920.314.1`, CPython 3.13.13, uv 0.11.19, pytest 9.1.1, and Aseprite
`1.3.18.5-dev` from the pinned official source. Runner names were
`GitHub Actions 1000019392` (cold Release), `GitHub Actions 1000019400` (warm CI),
and `GitHub Actions 1000019406` (routine PR).
The native setup summaries also retain CPU and memory facts. Both display
environment variables were absent. The same real `--batch --script` path was used.

All three used this native cache key; branch and PR cache visibility still follow
the existing GitHub cache scope:

```text
spa-aseprite-cli-Linux-X64-1.3.18.5-04b0a84617efb3107d380c352ebb0af9eb2633ff4c1a8bfcb671d2a437247d5d-0bf38469476a3e48e25583c3eb0b253373bc98c5bbb0dc0ac0b658ecbbee740d
```

The three E2E skips are two case-insensitive-filesystem cases and one macOS agent
sandbox case. They are the existing Linux exclusions. The full and routine reports
passed the nonempty, not-all-skipped JUnit execution check. Comparing their case
sets confirms that only the two complete wizard rebuilds are absent from routine CI.

## Revised owner limits — 2026-09-28

The owner rejected the provisional 75/80-minute proposal before merge. The fixed
limits are now **20 minutes for routine PR/push CI**, **40 minutes for nightly/manual
CI**, and **40 minutes for Release verification**. All automated gates exclude the
two complete example rebuilds. They retain the other native tests, both small
wizard probes, the hybrid hidden-pixel regression, and the exact-release-SHA gate.
Full asset reproducibility remains available through explicit local build/verify
commands and the retained `e2e and slow` tests.

The initial observations above are baseline evidence, not proof that the revised
limits are met. Removing both rebuilds projects the cold Release job from 62m 28s
to about 28m 2s; that subtraction is not an executed result. Routine CI already
excluded both rebuilds and took 27m 16s cold, so it requires a real build or test
execution improvement to fit 20 minutes. Candidate changes must be measured within
these fixed limits before acceptance. Splitting jobs does not by itself shorten
the total critical path.

These timeouts bound resource use and terminate unexpectedly long jobs. They are
not permission for indefinite increases. The full pytest times differed by about
18 minutes at the same revision; the observations do not isolate the execution
conditions causing that difference. In particular, the 25m 46s warm full job and
27m 16s cold routine job contain different test scopes and cannot measure cache
speedup. The warm cache hit and skipped compilation are directly recorded in the
log. A same-scope comparison and successful cold execution are needed for the
revised policy; a single sample does not guarantee capacity for future test growth.

## Revised execution evidence

The measured implementation is `176f368d74dd74ff790e1c50ddec6f76e113ce9c`.
It uses Clang 18 for the existing two-process Release build and two isolated
pytest-xdist workers for the required native tests. The pinned Aseprite source,
headless backend, native setup probe, installed-wheel checks, and retained test
assertions stay the same. The setup action hash gives the compiler change a new
cache identity; no cache entry was deleted or prewarmed outside the measured jobs.

The [cold PR CI job](https://github.com/aigengame/aseprite-automation/actions/runs/36376277594/job/108782715470)
passed at actual merge checkout `3c8919cfead2fe869c136bfb1da4b9dda83d2e40`.
It started at 04:06:19 UTC and completed at 04:20:54 UTC: **875 seconds
(14m 35s)**, leaving **325 seconds (5m 25s)** of its 20-minute limit.
All four CI jobs passed. The workflow creation-to-completion interval was
14m 55s, including its initial 20-second scheduling interval.

- Source download, configure, and build: 614.732 seconds; C/C++ configuration
  reports Clang 18.1.3. The verified native cache was saved at 04:17:06 UTC.
- Native OS dependencies: 17.137 seconds; cache lookup: 0.317 seconds;
  batch/script probe: 0.077 seconds; cache save: 1.346 seconds.
- Python setup in the native action: 5.652 seconds; wheel build/install:
  0.469 seconds; pytest: 220.39 seconds; JUnit upload: one second.
- Whole native action: 862 seconds. The remaining job time includes checkout,
  action setup, report upload, and cleanup.
- JUnit: 507 passed and the same three Linux platform skips. An exact comparison
  with the earlier routine report found the same 510 case identities and outcomes.
  It retains both small wizard probes and the hybrid hidden-pixel regression;
  neither complete rebuild appears in the report.

The [warm rerun of that PR job](https://github.com/aigengame/aseprite-automation/actions/runs/36376277594/job/108788150233)
used the same merge checkout. It recorded an exact cache hit and skipped compilation.
The [separate cold Release verification](https://github.com/aigengame/aseprite-automation/actions/runs/36376275936/job/108782666519)
checked out `176f368` directly and passed without creating or publishing a release.

| Measured phase, seconds | Cold PR | Warm PR | Cold Release |
| --- | ---: | ---: | ---: |
| Source download, configure, native build | 614.732 | 0, skipped | 1,429.703 |
| Native OS dependencies | 17.137 | 23.400 | 28.778 |
| Native cache lookup/restore | 0.317 | 1.970 | 0.492 |
| Native batch/script cache probe | 0.077 | 0.165 | 0.190 |
| Verified native cache save | 1.346 | 0, skipped | 1.727 |
| Python setup inside native action | 5.652 | 6.858 | 1.150 |
| Wheel build/install inside native action | 0.469 | 0.594 | 0.536 |
| Pytest | 220.39 | 427.41 | 410.46 |
| Whole native action | 862 | 462 | 1,874 |
| JUnit artifact upload | 1 | 2 | 1 |
| Whole job | **875 (14m 35s)** | **476 (7m 56s)** | **1,993 (33m 13s)** |
| Margin against that job's limit | 325 | 724 | 407 |

All three JUnit reports contain the same 510 case identities and outcomes: 507
passed and three unchanged platform skips. Both complete rebuilds are absent.
Release also passed source quality (15 seconds), fast tests (73 seconds; 275 passed
and four platform skips), metadata (less than one second), distributions and wheel
checks (two seconds), and distribution upload (two seconds). Its total job was
119 seconds longer than the native action. All three used Ubuntu 24.04 image
`20260920.314.1`, Aseprite `1.3.18.5-dev`, and the same source and compiler settings.
Runner names were `GitHub Actions 1000019465` (cold PR), `1000019467` (warm PR),
and `1000019462` (cold Release).

The warm run proves native cache reuse, but its longer pytest time offsets part
of the avoided build time. It must not be presented as an isolated compiler or
parallelism speedup. The cold Release build is also a counterexample to a robust
20-minute cold routine capacity claim: that build alone took 23m 50s. The logs show
the same 1,719-target build, with about 9m 19s of Ninja execution in PR and 22m 31s
in Release. The observations do not isolate the host conditions behind this spread.
All three workflow limits passed, but the routine cold-capacity criterion remains
open; one faster PR sample does not resolve the measured slower condition.

The next bounded candidate, `a76c88b`, used Clang `-O1 -DNDEBUG` in the Release configuration
to reduce compilation cost, while keeping the same native source, two build
processes, two test workers, and retained assertions. It records the CPU model,
available CPU count, and build wall/CPU time in the existing job log. This is a
functional test runtime; no Aseprite performance or bit-identical binary claim is
made. The [Clang command guide](https://clang.llvm.org/docs/CommandGuide/clang.html)
describes the optimization-level tradeoff. The observations below test that
configuration separately from the earlier passing jobs.

## Lower-optimization experiment and recovery boundary

The [cold PR attempt](https://github.com/aigengame/aseprite-automation/actions/runs/36379163478/job/108791119296)
tested head `a76c88b20fcbd6aa3ad66771087000f35b2d02ac` through actual merge
checkout `7e7c2395db40ffd56da33b119e04a80cf3fbb2e8`. GitHub explicitly annotated
the failure: "The job has exceeded the maximum execution time of 20m0s".
The job ran from 04:47:13 to 05:07:32 UTC, including timeout cleanup. Compilation
was cancelled at 05:07:26 UTC after 1,174.183 seconds in the download/configure/build
step; the last completed Ninja target was 1,611 of 1,719. It had a native cache miss,
Clang 18.1.3, and two available CPUs. The host model was AMD EPYC 7763; the model's
64-core label does not describe the two CPUs allocated to this runner.

The setup probe, cache save, installed-wheel step, and native tests were skipped.
There is no native JUnit report or native acceptance result for this attempt.
The three independent quality, fast-test, and package jobs passed. They do not
replace the missing native verification.

The [separate cold Release experiment](https://github.com/aigengame/aseprite-automation/actions/runs/36379173371/job/108791150928)
checked out `a76c88b` directly and used the same compiler profile. It passed in
**1,895 seconds (31m 35s)**, from 04:47:22 to 05:18:57 UTC, leaving **505 seconds
(8m 25s)** of the unchanged 40-minute limit. Draft creation, publication, and
Release PR maintenance were skipped by this manual verification path.

| Measured phase | Seconds |
| --- | ---: |
| Native OS dependencies | 15.587 |
| Cache lookup (miss) | 0.306 |
| Source download, configure, native build | 1,370.334 |
| Of native build: timed CMake/Ninja wall time | 1,297.029 |
| Native batch/script probe | 0.144 |
| Verified native cache save | 0.696 |
| Python setup inside native action | 1.115 |
| Wheel build/install inside native action | 0.319 |
| Pytest | 404.37 |
| Whole native action | 1,794 |
| JUnit artifact upload | 1 |
| Whole Release verification job | **1,895** |

The native JUnit report has the same 510 case identities and outcomes as the
previous Release report: **507 passed and three unchanged platform skips**.
Neither complete example rebuild ran. Source quality, fast tests (275 passed,
four platform skips), release metadata, distributions, and wheel checks also
passed. The runner was `GitHub Actions 1000019472`, with the same Ubuntu image
and AMD EPYC host model as the failed PR attempt and two allocated CPUs. The timed
build reported 40m 24.894s user CPU and 2m 21.482s system CPU against 21m 37.029s
wall time. This supports substantial use of both allocated CPUs during compilation;
it does not identify the cause of variation between separate runners.

The source/configure/build phase alone still exceeded the routine 20-minute
budget. This Release success establishes retained functional verification for
the profile, not acceptance of the routine cold path.

Backtrace conclusion: cache reuse is demonstrated by the earlier warm logs, and
routine CI already excluded both rebuilds before this timeout. The remaining cold
path places a full 1,719-target vendor runtime build before every required native
test when its cache is absent. A lower optimization level has not made that path
fit 20 minutes. The observations do not isolate the host conditions that caused
the build-time spread, so they do not establish a universal compiler speedup or a
specific host-contention diagnosis.

At this checkpoint, further compiler tuning was paused. The pending owner choice was whether to supply
one pinned private prebuilt runtime, with a separately bounded dependency build,
or retain compilation and provide a stronger Linux runner. These change dependency
ownership or runner cost and are not authorized by this failed experiment alone.
No new dependency workflow, artifact registry, or runner allocation was introduced.
The subsequent budget-boundary decision at the top of this document supersedes
that choice and keeps the existing source-build path.

## Release PR maintenance repair

The [first](https://github.com/aigengame/aseprite-automation/actions/runs/36299538289/job/108564547674)
and [second](https://github.com/aigengame/aseprite-automation/actions/runs/36299538289/job/108749676612)
maintenance attempts both validated the release metadata, committed the generated
lockfile, and pushed successfully. Both then exited with status 1 about 0.4 seconds
after the push, before CI dispatch. The logs did not retain the compared SHAs, so
an immediately stale PR API head is the strongest explanation, not a directly
observed remote value. There is no evidence of a full-E2E timeout in this failure.

The existing immediate head assertion is retained as a bounded convergence check:
at most ten reads with two seconds between mismatches. Each mismatch reports both
SHAs. Persistent mismatch or CLI failure still prevents dispatch. The controlled
external-CLI regression first failed against the immediate assertion, then passed
with the bounded wait; immediate agreement and permanent disagreement are also
covered. This is release-maintenance behavior, independent of the capacity budget.

On 2026-09-28 the owner chose to deliver this repair with #107 to `dev` and wait for
promotion to `main`. It does not retroactively repair the failed main run, authorize
publication, or require a new release process.

The later backtrace review identified a separate, patch-induced failure: extracting
dispatch into a repository script in `1a932e4` made its availability depend on the
checked-out Release branch. `0e0e7ff` copied that script to `RUNNER_TEMP` before
checkout. The owner approved removing this compensation and explicitly excluded
legacy Release-branch compatibility from the current scope. The action now owns
the bounded head check and dispatch inline; the helper, copy and legacy-branch
test are removed. Existing open-PR retry behavior remains.

The dispatch cases now execute the action's actual maintenance shell with a real
local Git origin and checkout. Three cases commit and push a lockfile change, then
cover immediate head agreement, delayed agreement and persistent disagreement. A
fourth retries a current Release PR with an unchanged lockfile and dispatches
without creating a commit. GitHub API responses, uv work and sleep are controlled.
These tests do not establish the original API-lag hypothesis or replace live
Release-maintenance evidence after promotion.
