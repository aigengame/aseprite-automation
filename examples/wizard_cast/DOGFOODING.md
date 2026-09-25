# SPA and gda workflow feedback

The reference run used a wheel-only SPA 0.1.0 installation from `dev` commit
`b19a249`, Aseprite 1.3.18.5-dev (API 41), gda 0.19.0, and Godot 4.6.3 on macOS.
SPA production code was unchanged by this example. Reproduce with the commands in
[README](README.md); each fresh output retains exact requests/results in
`evidence/operations.jsonl`, tool facts in `runtime.json`, and totals in `build.json`.
These timings are one local observation, not a benchmark or a support guarantee.

## Measured SPA friction

The reference 32-Frame build made 500 public CLI calls in 251.0 seconds. It produced
193 PNGs, seven editable Aseprite files, an asset manifest, and inspection evidence.

| Finding | Evidence and impact | Classification and disposition |
| --- | --- | --- |
| Repeated Cel placement/opacity writes dominate the recipe. | 240 `cel set` calls took 147.0 s. The public Descriptor excludes this Operation from Plans, so the workflow must invoke separate persisted Operations. Exact targets and inputs are retained in the operation log. | Enhancement candidate: assess bounded Plan eligibility for existing Cel updates in a separate SPA issue. The example uses the supported sequence; no Plan policy is expanded here. |
| Component/sequence export needs explicit orchestration. | 193 single-Frame `export image` calls took 61.4 s. Five component copies additionally require Layer visibility changes, position normalization, and fixed cropping. The complete run has 26 `layer set` calls (26.4 s), five copies (1.6 s), and five crops (1.9 s). | Existing requirements: [#59](https://github.com/aigengame/aseprite-automation/issues/59) owns Layer/region export, [#49](https://github.com/aigengame/aseprite-automation/issues/49) owns animation/sequence delivery. This example is concrete consumer evidence for those issues. Normalizing world motion remains recipe work. |
| A newly added Cel cannot choose a small Image size. | The source canvas is 128×96, while the gem is 5×5. The builder creates a transparent Cel, then calls `image resize` before painting. Six initial component Images need this step; one background Image also needs overscan. | Feature candidate: evaluate explicit small-Image creation with future Image authoring such as [#20](https://github.com/aigengame/aseprite-automation/issues/20). Current composition is correct and costs seven initial resize calls, so it does not block this slice. |
| The fixed Paint and Plan limits require request splitting. | The adapter splits runs at 256 addressed pixels and Plans at 64 Steps. Five Plan calls, including target painting and Cel creation, took 2.3 s. No pixels or errors were lost. | Declared limits, not a bug. [#26](https://github.com/aigengame/aseprite-automation/issues/26) can improve native drawing ergonomics, but raising Paint limits alone would not address the measured dominant cost. |
| Public rendered PNG checks cannot inspect hidden stored pixels. | Opacity-zero Cels and obscured Layers can hide bad source colors. A separate read-only native inspector checked 996,720 stored Image pixels, binary alpha, integer positions, and the 24-color set. It does not author or save. | Evidence gap related to the future raw Image surface in [#20](https://github.com/aigengame/aseprite-automation/issues/20). The independent test is sufficient for this finite tracer; no extra public inspection Operation is added. |

## gda observations

- There is no project-create command in the installed surface. A minimal
  `project.godot` was written, then public gda commands created/attached the main
  scene and scripts, imported assets, validated, ran tests, exercised the game,
  captured the viewport, and exported it. This is a small setup gap, not a failed
  gda contract or a reason to add a general scaffolding framework here.
- The import report identified all 193 requested PNGs. The source recipe inputs
  remain separate from generated `.import` files and engine cache. Imports and live
  checks ran in a disposable copy so the reusable source project did not acquire a
  developer-harness Autoload.
- Native UI Buttons need a complete press/release gesture. `input action` defaults
  to polling state; this demo handles events, so windowed evidence uses gda key or
  mouse input. The skill and live schemas document this distinction.
- A writable `--user-data-root` resolves restricted headless log/settings writes.
  Export-template discovery follows that redirect as well. This run used a private
  writable export root with access to the host's installed templates. A sandbox
  desktop-query denial was retried with the authorized windowed capability and
  succeeded. These are environment constraints, not SPA or gda product defects.
- The first universal macOS export reported that Godot required ETC2/ASTC import
  support. The project now enables `rendering/textures/vram_compression/import_etc2_astc`.
  Re-export and package startup passed. This was a consumer export configuration
  omission, not a gda command failure.

## Verification cost

The first Linux run at `394cb94` passed 275 real-runtime tests, with three platform
skips. The full recipe's two fresh builds took 734.8 seconds of the 1,004.3-second
E2E job. CI now runs one fresh build against the checked-in PNGs, complete bundle,
and reopened Aseprite metadata, Frames, Layers, Cels, and Tags. Native stored-pixel
inspection still covers the fresh build. The original local double-build evidence
and explicit two-build comparison command remain available. This preserves the
delivery assertions while reducing repeated work; it samples fewer fresh builds
per CI run. Final-run timing is recorded in the PR rather than promised here.

No new SPA or gda contract failure was confirmed in this run. An early fixture used
nonexistent Aseprite ColorSpace properties; native equality fixed the inspector.
The Godot consumer initially compared JSON-number dictionaries with integer
constants; comparing their numeric fields fixed loading. These were example/test
implementation defects and were repaired within this slice.
