# Issue #104: bounded local motion timing

On fixed 32-Frame wizard and emblem fixtures, one `motion apply` call and one
Plan containing a `motion apply` Step completed faster than 32 equivalent
standalone `cel set` calls. All three paths used the public CLI, normal native
save/reopen verification, and Target Commit. Separate native inspection of each
persisted result found equal Cel positions, opacity, stored pixels (including
transparent RGB data), Image dimensions, z-index, sharing facts, and Frame
durations. The source fixtures remained unchanged. Human review of animation
continuity is separate from this performance and state comparison.

## Source and workload

The measured Git HEAD was `2d5a5f0f72ed5e7b0a667c2e58471f67592e56a8`.
At snapshot time, the working tree had modified
`scripts/verify_installed_cli.py`, `src/spa/kernel/plan_run.lua`,
`src/spa/motion.py`, `src/spa/plan.py`, `tests/cli/test_e2e_manifest.py`,
`tests/motion/fixtures/poses.lua`, `tests/motion/test_e2e_motion.py`, and
`tests/runtime/test_e2e_aseprite.py`. It had untracked
`scripts/measure_motion.py`, `tests/motion/test_e2e_motion_sampling.py`,
`tests/motion/test_unit_motion.py`, and `tests/plan/test_e2e_motion_plan.py`.
The checkout was copied to a temporary snapshot before measurement so parallel
edits could not change a run. SHA-256 of the sorted list of relative paths and
file SHA-256 values under that snapshot's `src/` and `tests/`, excluding cache
directories, was
`e6ebcdd05e44b57149abaabf29ec2fab9d117a43af125d3fdcda60bb3b992ec2`
(239 files). In particular, the measured `src/spa/motion.py` SHA-256 was
`b5c068647058269b0584f26673592f4fbb382d6156101e22081bdd8b84cca480`,
and `src/spa/kernel/plan_run.lua` was
`6c2151138e7299c2c193d07d0e80ab010f999493a8529f58b7c1197d774c30b5`.
This identifies the uncommitted implementation beyond HEAD; it is not a Git tree
identifier.

Comparison with committed implementation `d7b02e3` found one production difference:
`motion.py` now rejects unknown private rejection codes explicitly. Successful
requests return before this branch. The sampling, native mutation/persistence,
and Plan source files are identical to the measured snapshot. Timings above are
still measurements of that snapshot, not a new run at `d7b02e3`.

Both inputs came from `tests/motion/fixtures/poses.lua` with `frame_count=32`,
`artwork=wizard` or `artwork=emblem`. The saved wizard input was 6,298 bytes,
SHA-256 `184dcce97a2d3ac1337df59b6bbd1b9fea79ea91638e6147f6e06a4ca8a18af3`;
the emblem input was 5,037 bytes, SHA-256
`4c116dde38d0c2b83d7c55dee23906e2c7a19a5d80626f012fa3be7c6146f0f2`.
Each path started from a fresh copy of its subject's input. Each subject had one
warmup run, then three measured runs. Execution was serial with concurrency one.
The runtime was macOS arm64 Aseprite `1.3.18.5-dev`, scripting API 41, and the
repository's temporary Python 3.13 environment. No production instrumentation
or verification bypass was used.

The curve used linear nearest-away-from-zero position offsets from `(0, 0)` on
Frame 1 to `(2, -2)` on Frame 32, and linear floor opacity from 0 to 255. The
standalone Cel requests used exact rational arithmetic to sample the curve and
added each offset to that Frame's authored position. Each Cel call wrote its
preceding result in place. Motion and Plan each used one in-place CLI call from
a fresh source copy. Each call retained normal save/reopen verification; the
Plan Step reports deferred verification and the enclosing Plan reports final
persisted reopen verification.

## Wall-clock results

Values are seconds from Python `time.perf_counter()` around public CLI
subprocesses. The standalone Cel row sums 32 complete calls. Warmups and
separate native output inspections are excluded. Ranges are the minimum and
maximum of three measured runs, without inferred confidence intervals.

| Frames | Fixture | Path | CLI calls per run | Median | Range |
| ---: | --- | --- | ---: | ---: | ---: |
| 32 | Wizard | `cel set` ×32 | 32 | 11.741 | 11.369–12.068 |
| 32 | Wizard | `motion apply` | 1 | 0.365 | 0.362–0.383 |
| 32 | Wizard | Plan with `motion apply` | 1 | 0.309 | 0.307–0.328 |
| 32 | Emblem | `cel set` ×32 | 32 | 11.849 | 11.511–12.164 |
| 32 | Emblem | `motion apply` | 1 | 0.376 | 0.363–0.380 |
| 32 | Emblem | Plan with `motion apply` | 1 | 0.323 | 0.312–0.327 |

A preliminary five-Frame run used the same method and one warmup plus three
measured runs per subject. Its medians were wizard: 1.792 s for five Cel calls,
0.363 s for motion, and 0.313 s for Plan; emblem: 1.804 s, 0.361 s, and
0.309 s, respectively. The 32-Frame data above are the primary observation.

The Plan versus standalone motion difference is about 0.05 seconds at these
medians; this test does not isolate its cause. These local small-fixture
measurements do not predict full wizard-scene runtime. They create no
performance quota or CI gate.

## Verification and reproduction

The companion [measurement script](../../scripts/measure_motion.py) runs the
three workflows and uses `tests/motion/fixtures/inspect.lua` through the test
helper after every timed workflow. It compares all persisted native Cel facts
across the paths. It also verifies source Frame durations, every stored Image
pixel value and dimension, z-index, sharing facts, and the untouched Layer
against the input. All warmup and measured cases passed.

From the frozen source state, with the normal SPA environment installed, run:

```sh
PATH=/private/tmp/spa-issue104-venv/bin:$PATH \
PYTHONPATH=/private/tmp/spa-issue104-performance-snapshot/src:/private/tmp/spa-issue104-performance-snapshot \
SPA_TEST_ASEPRITE=/Users/lelej/Applications/Aseprite-v1.3.18.5.app/Contents/MacOS/aseprite \
python scripts/measure_motion.py --frames 32 --output /private/tmp/spa-issue104-performance-results-32
```

The temporary output directory contains generated Sprite files and `raw.json`
with per-call timings, input hashes, native-equality results, and warmup flags.
Change the temporary environment, snapshot, and Aseprite paths for another host.
Generated fixtures and results are outside the repository.
