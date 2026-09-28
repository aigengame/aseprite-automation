# Linux full-E2E capacity — issue #107

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

## Current observations

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
(27m 16s), leaving 764 seconds (12m 44s) of the unchanged 40-minute budget.
Both complete wizard rebuilds were deselected, as required for PR events.
The additional head changes only release maintenance, its three fast regression
tests, and release documentation; it does not change the native workload.

All three jobs used Linux X64, Ubuntu 24.04 image
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
