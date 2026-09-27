# Issue #105: bounded Cel Plan profiling

Baseline measurements preceded Plan evaluation. Baseline revision was
`f1ebf9c1ef91fbf9388e8e527614109f39bab509`; the standalone/Plan comparison used
`1cdd977e1f7c44b7e8bca0c078582e4fd263e662`. The accompanying
[`issue-105-profile.json`](issue-105-profile.json) records exact requests,
individual timings, totals, and fixture identity.

## Fixed scope

The unmodified tracked `examples/wizard_cast_v2/source/wizard_scene.aseprite`
was restored before each workload: SHA-256
`bd41851296ed0172d9565a1e413127fd2ee20476c8665ac69be7f7a0a430a56c`,
1,174,000 bytes, 384×288 pixels, 32 Frames, seven Layers, and 224 Cels.
Aseprite reported `1.3.18.5-dev`, scripting API 41, on macOS arm64; Python was
3.13.13. Packaged native probe fixtures were hydrated before measurements.
Concurrency was one, with other task Aseprite tests paused. Each workload was
measured once; these are bounded observations, not distribution estimates.

The Cel workload updates placement, opacity, and z-index of existing wizard
Layer `[3]` Cels at Frames 1, 5, 9, 13, 17, 21, 25, and 29. It includes a
zero-opacity write. Standalone calls update their preceding output in place;
the Plan applies exactly the same eight requests to its own fresh source copy.

The baseline Layer diagnostic hides background `[1]`, stars `[2]`, and sparks
`[5]` as representative export-preparation writes. No export runs or Layer Plan
eligibility changes are included; export-specific work remains owned by #59.

## Observed wall time

All times below are aggregate seconds. `Checks` includes pre-save target
resolution, native postcondition checks, Image digests, rendering where required,
and the live persistence snapshot. `Reopen/verify` includes close, reopen,
persisted snapshot, and native state/pixel verification.

| Revision / workload | CLI / native calls | Total | Open | Mutation | Checks | Save | Reopen/verify | Other |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline, 8 Cel writes | 8 / 16 | 27.697847 | 0.569278 | 0.000619 | 10.461077 | 2.706754 | 11.012638 | 2.947481 |
| Baseline, 3 Layer writes | 3 / 6 | 23.766358 | 0.223767 | unresolved | 15.538870 | 1.081706 | 5.753045 | 1.168971 |
| Implementation, 8 standalone Cel writes | 8 / 16 | 35.608433 | 0.723391 | 0.000903 | 13.788252 | 3.526031 | 13.720617 | 3.849239 |
| Implementation, one 8-Step Cel Plan | 1 / 1 | 4.880641 | 0.088914 | unresolved | 2.153501 | 0.426925 | 1.817772 | 0.393529 |

Standalone invokes a compatibility probe and an Operation handler per request.
Plan probes capabilities in its single process. The Plan trace contains eight
mutation brackets and one final save/reopen bracket. Full persistence
verification remained enabled. Repeated native checks and persisted work dominate
these measurements. The two revision runs occurred at different times; the higher
standalone time in the later run alone does not establish a regression. The Plan
observation is specific to this document, machine, and workload and promises no
general speedup.

## Timing method and verification

Temporary Lua instrumentation flushes stage markers to stdout; the existing SPA
Python reader timestamps arriving chunks using monotonic `time.perf_counter()`.
No Lua CPU clock is labeled as wall time. Start/end markers received in one chunk
are unresolved, represented as zero in the machine data; tiny setter timings
should not be interpreted as precise native duration. Scheduling and tracing costs
remain included. `Other` is total CLI wall time minus measured intervals: Python
startup/validation, compatibility probing, process startup/exit, transport,
staging/Target Commit, and instrumentation overhead. It is not solely process
startup time.

All measured requests succeeded with persisted reopen verification. A separate
native invocation compared all 224 Cels across the original source and both final
outputs. Every stored Image byte string and Image dimension matched the source;
standalone and Plan positions, opacities, and z-indices matched each other. All
pairwise sharing facts were preserved (this wizard fixture has no linked Image
pairs). The outputs contained four zero-opacity Cels. Linked and hidden Layer
boundaries are covered by the dedicated native acceptance tests, rather than
claimed from this fixture.

All eight Step results matched the corresponding standalone `before_cel_count`,
`before_cels`, `affected_cels`, and `cel` facts. Each Step reports
`persisted_reopen_verified=false`; only the enclosing Plan reports the final
persisted reopen verification. Later changes in this PR add tests and this report
without changing the measured production code.

Reproduction uses a temporary clone at each exact revision, hydrated LFS files,
the listed requests, and the same serial ordering. One-off instrumentation patches
and raw reader traces/results are retained with the task evidence; no production
profiling API, verification bypass, or benchmark subsystem was added. The first two
trial runs had unhydrated probe fixtures and were discarded before this baseline.
