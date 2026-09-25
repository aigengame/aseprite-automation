# Moonlit Spell Practice

A wizard raises a gem staff, gathers sparks, and casts at a moving target. This
[issue #19](https://github.com/aigengame/aseprite-automation/issues/19) example uses
installed SPA and real Aseprite to author the art, then gda and Godot to consume it.

![The SPA-authored casting Frame](godot/content/wizard_assets/scene/0015.png)

## Play

Open `godot/project.godot` in Godot 4.6 and run the main scene. The delivered macOS
application can run without an editor, SPA, Aseprite, Python, or gda.

- Press **Space** or click **CAST** to start a spell. Anticipate the moving target:
  charging takes one second, then the projectile must travel to the target.
- Charge and recovery reject repeated input. A round contains five casts.
- Read the **HIT / MISS** feedback and the result. Press **R**, **Enter**, or
  **AGAIN** to restart. **Escape** or **QUIT** exits.

The logical viewport is 128×96. Nearest texture filtering and integer scaling keep
art pixels crisp. A resizable window starts at 768×576. UI text belongs to the
Godot consumer; it is not baked into the reusable art.

## Reuse the assets

Run `git lfs pull` after checkout. PNG files use the repository's Git LFS rules.

| Artifact | Purpose |
| --- | --- |
| `recipe.json` and `art.py` | Finite art inputs and deterministic sampling into integer pixels. |
| `source/wizard_scene.aseprite` | Editable, layered 128×96 source with 32 Frames and four Tags. |
| `source/target.aseprite` | Editable target. Other `.aseprite` files are derived component work copies. |
| `godot/content/wizard_assets/bundle.json` | Generated palette, durations, phase ranges, dimensions, anchors, and release Frame. |
| `godot/content/wizard_assets/{wizard,gem,burst,projectile,background,target}/` | Reusable ordered PNG components. |
| `godot/content/wizard_assets/scene/` | Ordered full-scene Frames for tracer review. |

The generated bundle uses one-based Frame Numbers. The recipe uses zero-based
indices. Each animated component has 32 PNGs at 100 ms per Frame; an inactive
effect can be fully transparent. The target has one Frame. Phase ranges are IDLE
1–4, CHARGE 5–14, CAST 15–20, and RECOVER 21–32. The scene loop returns from Frame
32 to Frame 1. These are explicit consumer choices; the example does not infer
playback from Tag `repeats=0`.

Place a component's upper-left corner at `world_position - anchor`. The wizard
anchor is its foot, the target anchor is its bullseye, and the projectile anchor
is its head. Component PNGs retain local pose motion and remove baked scene shake
and projectile travel. The wizard clip includes its gem and cast sparks/burst;
the separate effect clips also work at another position. Use CAST for an emitted
projectile or hit burst. The Godot consumer loops the projectile's CAST clip during
flight and plays the hit burst once. Its collision and flight are runtime rules.

The example remains outside SPA production modules. It adds no public Operation,
generic animation engine, or asset framework. The recipe is a maintained example,
not a schema for arbitrary art. Change the recipe/sampler, regenerate both source
and PNG delivery, and rerun verification together.

## Rebuild with installed SPA

From the repository root, install this branch's wheel in a separate environment:

```sh
uv build --out-dir /tmp/wizard-dist
uv venv --python 3.13 /tmp/wizard-spa
uv pip install --python /tmp/wizard-spa/bin/python /tmp/wizard-dist/*.whl

uv run --frozen python -m examples.wizard_cast.build \
  --spa /tmp/wizard-spa/bin/spa \
  --aseprite /path/to/aseprite \
  --output /tmp/wizard-build-a
```

Use fresh output paths. No art asset or network input is read during generation;
package installation is a separate setup step. One measured macOS build made 500
public SPA calls in 251 seconds; this is an observation, not a performance promise.
The output contains `source/`, `assets/`, `recipe.json`, and `evidence/`.

`evidence/operations.jsonl` records exact public requests, results, and elapsed time.
Other evidence includes reopened Sprite facts, a complete declared Cel/duration
audit, two real gem resizes with explicit pivot rounding, and a first/last Frame
comparison and Preview. The Preview can contain blended colors; it is a review
artifact and is not part of the fixed-palette asset bundle.

Build again at `/tmp/wizard-build-b`, then compare both and the delivered assets:

```sh
uv run --frozen python -m examples.wizard_cast.verify \
  /tmp/wizard-build-a /tmp/wizard-build-b \
  --delivered-assets examples/wizard_cast/godot/content/wizard_assets
```

Verification compares reopened structure and decoded RGBA pixels, not Aseprite
file bytes. It checks phase coverage, timing, component dimensions, declared colors,
binary alpha, gem opacity, and independent resize effects. The real-runtime test
also opens the saved source with a read-only Lua inspector to check stored pixels
in invisible Cels. That inspector never authors or saves art.
CI makes one fresh build and compares it with the checked-in PNGs, bundle, and
reopened Aseprite source. The two-build command above is available for explicit
repeat-run checks; the original local double-build observations are retained in
[asset evidence](evidence/asset-verification.json).

After an intentional recipe change, replace the checked-in `source/` and
`godot/content/wizard_assets/` from the verified output. Retain generated metadata;
do not separately hand-edit the animation timeline in Godot.

## Verify and export the Godot consumer with gda

Tested tools: gda 0.19.0 and Godot 4.6.3. Set `GDA_GODOT` or pass `--godot` when
Godot is not discovered automatically. Use a writable `--user-data-root` for
headless work in a restricted environment. Do not redirect it for export unless
the matching export templates are also installed there.

```sh
gda resource import res://content/wizard_assets/wizard/0001.png --project examples/wizard_cast/godot --json
gda scene validate res://main.tscn --project examples/wizard_cast/godot --json
gda scene preflight res://main.tscn --project examples/wizard_cast/godot --json
gda script run res://tests/round_rules.gd --strict --project examples/wizard_cast/godot --json
gda script run res://tests/playable_round.gd --strict --project examples/wizard_cast/godot --json
gda export run --preset macOS --project examples/wizard_cast/godot --json
```

Check `valid`, startup status, child exit status, and diagnostics in gda results;
a successful command envelope alone is not a passing test. The export preset needs
the matching Godot macOS templates. It includes `bundle.json`, excludes test code
and the developer harness, and produces a local unsigned, non-notarized build.
The first missing-texture request triggers Godot's project-wide import pass.

For windowed gda input and screen capture, use a disposable copy of the project:
`daemon start` installs its harness in that copy. Stop it after verification. The
source/export project has no harness Autoload. Asset import creates Godot cache
and `.import` sidecars; these are disposable and not authoring inputs.

## Ownership and evidence

`systems/target_practice.gd` owns cast admission, one release per cast, outcomes,
round completion, and restart. Content owns assets, animation, target motion, and
collision. UI presents Content state and sends player actions. `main.gd` only
composes Content and UI. No Add-on or Autoload is needed.

SPA owns Aseprite mutation, persistence, and PNG export. Frame copies keep Images
independent before each native resize. Plans contain only Descriptor-eligible Steps;
other Operations run in sequence. To derive components, copy the source, select
visible Layers, normalize positions, then crop. Crop removes out-of-bounds pixels.

[Tool feedback](DOGFOODING.md) records measured friction and its disposition.
[Test guidance](../../docs/testing.md) separates Linux headless SPA evidence from
local graphical Godot evidence. Human acceptance of the silhouette, phase clarity,
magic progression, loop continuity, and play feel remains a separate PR review.

[Godot evidence](evidence/godot-verification.json) records source test results,
windowed input coverage, and the local package digest and checks. The package is
unsigned and not notarized. The PR and local handoff link the playable ZIP; a fresh
checkout can reproduce it with the export preset above.

![A real gda-driven hit](evidence/playable-hit.png)
![The end-of-round view](evidence/playable-results.png)
