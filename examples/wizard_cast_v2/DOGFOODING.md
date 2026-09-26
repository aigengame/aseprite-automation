# Hybrid wizard workflow feedback

Issue [#100](https://github.com/aigengame/aseprite-automation/issues/100) is a finite
experiment. SPA production remains unchanged. The baseline is dev commit
`e4ce2f585c36bb3c349f7f81bb4953ced543a5f0`, built as SPA 0.1.0 and installed from its
wheel in a separate environment. Local tools: Aseprite 1.3.18.5, gda 0.19.0,
Godot 4.6.3, and Pillow 12.3.0. Linux and final human evidence remain pending.

## H01 — Generated art needs an explicit preparation stage

- **Step/tool:** concept generation, built-in `image_gen.imagegen`; model not
  reported. The selected original is `inputs/raw/idle-concept.png`.
- **Expected/observed:** the prompt requests the 24-color palette and crisp alpha.
  The original instead contains 262,645 distinct RGBA values and all 256 alpha
  values. Its logical pixel scale also differs from the requested small sprite.
- **Evidence/reproduction:** `inputs/prompts/01-idle-concept.txt`, original file,
  and `inputs/preparation-evidence.json`. Run the example's `prepare` module.
- **Impact/workaround:** palette and alpha cannot be trusted directly. The finite
  preparation thresholds alpha at 128, resizes with nearest-neighbor, maps RGB to
  the nearest declared color without dithering, and records crops and hashes.
  The first candidate has 12,219 visible pixels in a 160×204 raster.
- **Cost/category/disposition:** 37.6 seconds observed for the first generation;
  preparation effort and later revisions are recorded separately. This is an
  art-input and hybrid-workflow limitation, not a SPA defect. Retain raw and
  prepared inputs; future import feedback belongs to #46.

## H02 — Existing Pixel Patch can bridge a frozen PNG

- **Step/tool:** prepared PNG → SPA 0.1.0 → real Aseprite → PNG → gda import.
- **Expected/observed:** public operations successfully authored three independent
  Frames, changed one Cel position and hid another, reopened the file, and exported
  exact expected RGBA values. gda imported all three PNGs.
- **Evidence/reproduction:** run `python -m examples.wizard_cast_v2.probe` with an
  installed `--spa`, local `--aseprite`, and fresh `--output` directory.
  `evidence/handoff*.json` records the observations, native stored colors and import.
- **Impact/workaround:** 256 addressed pixels per Patch and 64 Steps per Plan require
  example-owned decoding and batching. The small proof took 11 CLI calls and
  4.35 seconds of SPA process time. It does not prove the full animation cost.
- **Category/disposition:** verified feasible adaptation; import enhancement #46.
  Keep the bounded adapter in v2. No production import API or limit was added.

## H03 — Transparent export pixels can retain hidden RGB

- **Step/tool:** zero-opacity Cel export in the three-Frame probe.
- **Expected/observed:** the first test oracle assumed every transparent pixel was
  `(0,0,0,0)`. Aseprite exports zero alpha while retaining the hidden Image RGB.
  Visible Frames were already exact; native inspection found no invalid alpha or
  undeclared stored color.
- **Evidence/reproduction:** `probe.py` Frame 3, with the same prepared Image and
  Cel opacity 0; `evidence/handoff-native.json` checks invisible stored pixels.
- **Impact/workaround:** correct the example oracle to check preserved RGB and zero
  alpha explicitly. Do not alter valid production behavior to satisfy an incorrect
  oracle. One failed 11-call probe and one successful rerun were required.
- **Category/disposition:** example verification assumption, resolved locally.
  Repeatability still compares complete decoded RGBA bytes, including hidden RGB.

## H04 — Godot needs a writable data location in the managed sandbox

- **Step/tool:** gda 0.19.0 `scene validate`, Godot 4.6.3.
- **Expected/observed:** the default Godot application-data path was not writable;
  engine stderr reported directory creation failure despite a structured verdict.
- **Evidence/reproduction:** project name `Moonlit Spell Practice V2` with the
  default data root in the managed macOS environment.
- **Impact/workaround:** use gda's existing `--user-data-root` with a writable
  temporary path for validation. The retry passed; 87 round-rule checks passed.
- **Category/disposition:** environment limitation; documented command setup.
  Asset import, gameplay, graphical input and final HITL remain distinct evidence.

## H05 — Larger native documents make separate placement calls expensive

- **Step/tool:** full 384×288 authoring through SPA 0.1.0. The Canvas has nine
  times v1's pixel area; the wizard component also reserves space for larger poses
  and effects. Compare resolutions and actual call scopes, not elapsed time alone.
- **Expected/observed:** the first full-build preview measured a mean of 3.0869
  seconds across 56 `cel set` calls. These calls persist and verify the full
  document. `cel set` is not eligible for an Operation Plan in this installation.
- **Impact/workaround:** set Frame 1 placement before independent Frame copies,
  then change only Cels whose placement/opacity differs from that inherited value.
  This finite builder change reduces source placement calls from 196 to 127.
  A real three-Frame probe confirmed inherited position and unchanged Frame 1/3
  pixel digests after Frame 2 placement, opacity and native resize changes.
- **Cost/category/disposition:** 69 fewer calls; about 213 seconds saved is an
  estimate from the old mean, not a measured optimized total. Full timings are
  recorded after completion. This is workflow friction and a candidate for future
  Plan coverage/performance work, not permission to change SPA schemas here.
  Linking unchanged Images alone would not remove current per-Cel inspection cost.

## H06 — Pose identity does not supply alignment or attachment metadata

- **Step/tool:** five reference-guided wizard poses from built-in imagegen.
- **Expected/observed:** hat, beard, outfit and staff remain recognizable, but robe
  contours, hand placements, staff angles and image bounds differ. The peak-charge
  staff ends close to the raw image boundary. A fixed bounding-box fit would change
  body scale when the staff/cape expands.
- **Evidence/reproduction:** `inputs/provenance.json`, per-pose raw foot/gem
  landmarks in `inputs/preparation.json`, and `evidence/prepared-poses.png`.
- **Impact/workaround:** apply the same 1/8 scale to every character pose, align
  explicit foot landmarks to (84,212), and declare the measured gem attachment per
  pose. Retain five static poses; numeric motion/effect rules fill the 32-Frame
  schedule. The prepared character canvas is 224×224. No anatomy interpolation or
  complete procedural redraw was introduced.
- **Category/disposition:** art-input consistency and authoring metadata gap. The
  pose contact sheet and first real SPA CAST preview were inspected by the agent;
  costume continuity and motion quality still need final human review. Input
  preparation and attachment rules remain example-owned feedback for #46/#57.

## H07 — Matching delivery PNGs does not establish native repeatability

- **Step/tool:** local two-build verification, SPA 0.1.0 and Aseprite 1.3.18.5.
- **Expected/observed:** an initial comparison checked saved JSON and exported
  PNGs. Independent review found that it could miss changes in a hidden Cel.
  A real regression changed a stored pixel on a hidden Layer with zero Cel
  opacity; all three exported RGBA images remained equal.
- **Evidence/reproduction:** `tests/examples/test_e2e_hybrid_native.py` passed
  locally in 12.50 seconds. `native_inspection.py` reopens each document through
  SPA and supplements it with read-only full RGBA inspection. Both the local
  comparison and full E2E now use this check for all seven native files.
- **Impact/workaround:** rendered output alone is insufficient. The shared check
  rejects the hidden-pixel counterexample and requires actual native files, not
  cached evidence. Independent re-review of commit `de92a71` confirmed closure.
- **Category/disposition:** resolved example-verification defect. Native pixel
  observation remains feedback for [#20](https://github.com/aigengame/aseprite-automation/issues/20);
  the inspector does not author or save assets.

## Generation and preparation cost

Nine imagegen calls produced five character concept/pose inputs and four
auxiliary assets; all nine selected originals are retained. No auxiliary v1
art is reused. The first five request durations total 192.9 seconds. Background
and target were generated together in a measured 50.1-second interval; projectile
and burst together in 75.9 seconds. The sum of these recorded request/group
durations is 318.9 seconds. It is not total creative elapsed time or an estimate
of individual parallel request costs. The tool did not report a model identifier.

The eleven prepared rasters contain 384,649 pixel slots and 179,960 visible
pixels. A separate preparation rerun took 1.660 seconds and reproduced every
prepared-file hash and preparation fact. This covers threshold, crop, resize,
palette mapping and serialization only; prompt choice, landmark selection,
code authoring and visual correction effort were not timed. See
`evidence/preparation-reproduction.json`. Concurrent SPA builds were running.

The character treatment needed one initial size candidate and then a shared
1/8 scale with five explicit foot/gem landmark pairs. Retained edits also separate
the gem from the wizard raster and extract a small spark stamp from the generated
burst. These are bounded, declared corrections. Imagegen did not provide usable
anchors, exact palette membership, binary alpha, or deterministic intermediate
poses by itself.

## Evaluation against v1

The baseline is the unchanged `wizard_cast` at the pinned dev commit above.
The agent inspected actual SPA exports at both their native resolution and a
common display footprint. Final human preference and play acceptance remain open.

| Dimension | Observed benefit | Remaining cost or limit |
| --- | --- | --- |
| Art detail | Generated costume trim, beard, carved staff, stonework and rune effects survive the declared preparation and SPA export. | Palette reduction loses some raw shading. Increased resolution contributes to the result; this is not an equal-resolution comparison. |
| Motion control | The same frozen inputs produce an explicit 32-Frame schedule. Pose choice, attachments, effects and offsets can change without imagegen. | Five static poses still make discrete transitions. Numeric motion does not supply natural in-between anatomy or perfect costume continuity. |
| Revision | Foot and gem landmarks give stable placement; component exports retain explicit anchors. | Each replacement pose needs preparation and attachment checks. Changing an arbitrary body angle can require a new generated or corrected pose. |
| Reuse and consumption | The six component roles and schema 1 are unchanged. The independent Godot project uses the same five-cast rules and native animation. | Canvas size, layout, target bounds and collision radii must be adapted to the declared v2 geometry. |
| Engineering control | Frozen, versioned rasters remove generation variance and credentials from normal builds and CI. SPA owns all native writes and PNG exports. | The example must decode PNGs, split Pixel Patches, place Cels and orchestrate sequence/component exports. |
| Workflow effort | imagegen supplies richer starting pixels than the hand-coded v1 character. | This adds preparation and art-consistency work, and larger native documents increase SPA execution cost. No measured total creative-time comparison is available. |

The outcome is mixed: the hybrid path improves the retained visual detail and
keeps asset production repeatable, while preparation, pose continuity and full
rebuild cost remain substantial. It is suitable for this bounded pose library;
it does not establish a general animation engine or prove that imagegen can
produce an arbitrary consistent animation sequence.

Follow-up ownership remains narrow: [#46](https://github.com/aigengame/aseprite-automation/issues/46)
for raster import, [#20](https://github.com/aigengame/aseprite-automation/issues/20)
for stored Image observation, [#49](https://github.com/aigengame/aseprite-automation/issues/49)
and [#59](https://github.com/aigengame/aseprite-automation/issues/59) for sequence and
component export, and [#57](https://github.com/aigengame/aseprite-automation/issues/57)
for later integration evidence. Motion/attachment rules are candidates for later
reusable capability only after a separate domain decision. This experiment adds
no SPA production code or public contract.
