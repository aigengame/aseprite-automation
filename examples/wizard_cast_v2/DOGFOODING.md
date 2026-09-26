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
