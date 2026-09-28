# Linux CI capacity — issue #107

## Current acceptance

The owner-approved 20/40/40-minute limits and removal of both automatic example
rebuilds are implemented. Capacity acceptance remains open. The `a76c88b` cold PR
attempt exceeded its 20-minute limit before native compilation finished; the
required E2E suite did not start. PR #121 remains draft. A dependency-provisioning
or runner change requires the pending owner decision described below.

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

Further compiler tuning is paused. The pending owner choice is whether to supply
one pinned private prebuilt runtime, with a separately bounded dependency build,
or retain compilation and provide a stronger Linux runner. These change dependency
ownership or runner cost and are not authorized by this failed experiment alone.
No new dependency workflow, artifact registry, runner allocation, or larger budget
has been introduced. A private runtime artifact, if approved, must be built for
the pinned dependency rather than as a serial prerequisite of each SPA test run.

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
