# Moonlit Spell Practice — hybrid workflow

This isolated [#100](https://github.com/aigengame/aseprite-automation/issues/100)
example uses actual imagegen concept and key-pose pixels, finite Python assembly,
the unchanged public SPA CLI, and a Godot consumer. The v1 example is a reference;
v2 has no runtime dependency on its directory.

## Play and reuse

The source project is `godot/project.godot`. Godot 4.6.3 is the locally verified
engine. Press **Space** or click **CAST**, time the spell to hit the moving target,
and complete five casts. **R**, **Enter**, or **AGAIN** restarts; **Escape** quits.
The viewport is 384×288 with nearest filtering and integer display scaling.

| Artifact | Owner and purpose |
| --- | --- |
| `inputs/raw/`, `inputs/prompts/`, `inputs/provenance.json` | Selected original imagegen outputs, exact prompts and reference relationships. |
| `inputs/preparation.json`, `prepare.py` | Explicit alpha, palette, scale and anchor preparation. |
| `inputs/prepared/` | Frozen contract-valid rasters; normal builds use these without generation or credentials. |
| `recipe.json`, `art.py` | Pose selection, timing, attachments, movement, palette rim light and effect assembly. |
| `source/` | Seven editable SPA-authored Aseprite documents. |
| `godot/content/wizard_assets/` | Bundle schema 1, 161 component PNGs and 32 review-scene PNGs. |
| `evidence/` | Input handoff, technical checks and review materials. Human acceptance is separate. |

All PNG and Aseprite files use Git LFS. Run `git lfs pull` after checkout.
The bundle owns actual dimensions, anchors, phases and muzzle position. Place a
component at `world_position - anchor`; wizard uses a foot anchor, target a
bullseye, and projectile its head. Scene shake and projectile world travel are
removed from reusable component exports. The wizard clip includes its own gem
and casting effects; the separately exported effect clips can be reused elsewhere.

The timeline remains 32 Frames at 100 ms: IDLE 1–4, CHARGE 5–14, CAST 15–20 and
RECOVER 21–32. The game loops IDLE, emits at Frame 15, and plays the other phases
once per cast. Scene review loops Frame 32 back to Frame 1. These are explicit
example rules, not an inferred interpretation of Tag `repeats=0`.

## Review materials

- [Full 3.2-second scene loop](evidence/scene-loop.webp) and
  [selected exported Frames](evidence/scene-keyframes.png).
- [Prepared poses](evidence/prepared-poses.png),
  [v1 and v2 at a common display footprint](evidence/v1-v2-comparison.png), and
  [CAST at the default 2× game scale](evidence/cast-at-display-size.png).
- Actual Godot captures: [idle](evidence/playable-idle.png),
  [hit](evidence/playable-hit.png), and [results](evidence/playable-results.png).
- [Asset verification](evidence/asset-verification.json),
  [Godot verification](evidence/godot-verification.json),
  [motion revision](evidence/motion-revision.json), and
  [SPA production boundary](evidence/production-boundary.json).

The scene preview uses only SPA-exported PNGs; it is not a recording of gameplay.
The source Godot project is the playable delivery. No standalone package is
included in v2.

## Reproduce with unchanged SPA

From the repository root, build and install the wheel separately. Supply the
actual Aseprite executable for your host; no local application path is a default.

```sh
uv build --out-dir /tmp/hybrid-dist
uv venv --python 3.13 /tmp/hybrid-spa
uv pip install --python /tmp/hybrid-spa/bin/python /tmp/hybrid-dist/*.whl
uv run --frozen python -m examples.wizard_cast_v2.probe \
  --spa /tmp/hybrid-spa/bin/spa --aseprite /path/to/aseprite \
  --output /tmp/hybrid-probe
uv run --frozen python -m examples.wizard_cast_v2.build \
  --spa /tmp/hybrid-spa/bin/spa --aseprite /path/to/aseprite \
  --output /tmp/hybrid-build-a
```

Use a fresh output directory. The build outputs `source/`, `assets/`, `recipe.json`
and `evidence/`. Its public requests and results are in `evidence/operations.jsonl`;
input file hashes, reopened Sprite facts, native scale results and call timing are
recorded separately. It does not generate artwork, fetch remote inputs or need API
credentials. Preparation can be reproduced explicitly with
`python -m examples.wizard_cast_v2.prepare`; it is not part of a normal build.

Build a second time at `/tmp/hybrid-build-b`, then compare both and the delivery:

```sh
uv run --frozen python -m examples.wizard_cast_v2.verify \
  /tmp/hybrid-build-a /tmp/hybrid-build-b \
  --spa /tmp/hybrid-spa/bin/spa --aseprite /path/to/aseprite \
  --delivered-assets examples/wizard_cast_v2/godot/content/wizard_assets
```

The comparison reopens all seven native files in each build, reads every saved
Cel, including invisible Cels, and compares structure and stored RGBA digests.
Full E2E uses the same native inspector. Both also compare decoded delivery PNGs;
neither requires identical native file bytes. The read-only inspector does not
author or save assets. A single build path runs offline artifact checks only.
Changing `motion.idle_bob_pixels` in a recipe copy is a bounded revision: pass the
copy through `--recipe` and rebuild using the same frozen inputs. The clock and
phase ranges remain unchanged.

## Verify the Godot consumer

```sh
gda resource import res://content/wizard_assets/wizard/0001.png --project examples/wizard_cast_v2/godot --json
gda scene validate res://main.tscn --project examples/wizard_cast_v2/godot --json
gda scene preflight res://main.tscn --project examples/wizard_cast_v2/godot --json
gda script run res://tests/round_rules.gd --strict --project examples/wizard_cast_v2/godot --json
gda script run res://tests/playable_round.gd --strict --project examples/wizard_cast_v2/godot --json
```

Inspect validation verdicts, child exit status and diagnostics; an exit-zero
envelope alone is insufficient. In a restricted environment, put gda's global
`--user-data-root /writable/path` before the command. For windowed input and screen
capture, use a disposable project copy so the daemon harness does not enter the
delivered source. A separate macOS package is optional.

The [Godot ownership map](GODOT_ARCHITECTURE.md) applies Systems, Content and UI
with a thin composition root. No shared Add-on or Autoload is needed.

Routine Linux E2E includes the small generated-raster handoff probe. The complete
rebuild is `e2e` + `slow` and runs locally on demand. All automated CI, nightly,
manual Actions, and Release gates exclude it, while retaining the small handoff
and hidden-pixel comparison tests. See the repository
[test policy](../../docs/testing.md#complete-example-rebuilds). Local macOS,
Linux headless, Godot graphical input and final human review are separate evidence.

## Evaluation

[DOGFOODING.md](DOGFOODING.md) records actual attempts, adaptation costs, findings
and follow-up ownership. The richer raw concept alone is not acceptance: inspect
prepared poses, SPA-exported motion and the actual game display. Final visual and
play acceptance remains pending until the completed delivery receives HITL review.
SPA production modules, schemas and limits remain unchanged.
