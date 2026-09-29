# Native Fill, Pencil, and Eraser evidence

## Scope and environment

This record supports [issue #27](https://github.com/aigengame/aseprite-automation/issues/27).
The issue owns the approved feature contract. ADR-0018 and ADR-0060 retain the
native algorithm and private Tool boundary; this slice does not change them.

The local runtime is macOS Aseprite `1.3.18.5-dev`, API 41. Source inspection used
upstream commit `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9` (tag `v1.3.18.5`).
The binary's exact build provenance is not established by that source checkout.
Linux remains a separate verification environment. Each installation admits the
operations and gesture algorithms through its own packaged native probes.

## Findings that shaped the adapter

| Native fact | Consequence and retained check |
| --- | --- |
| Paint Bucket and Magic Wand use the same native flood-fill point shape (`data/gui.xml`, `src/app/tools/point_shapes.h`). | Observe matching with Magic Wand before painting. This retains requested coverage when the paint color already matches or opacity produces no change. The Fill tests compare coverage, changed counts, and saved pixels with independent native calls. |
| Enlarging the temporary Canvas enlarges the Fill domain. A `Sprite(source)` copy resets the Grid bounds. | Keep the original Canvas and copy the saved `gridBounds` explicitly. Tests cover small offset Cels, outside-Canvas seeds, clipping, and shifted Grid origins. |
| An active native Selection constrains flood traversal. | The owner approved shared SPA Selection Application after matching. The two-endpoint Selection counterexample verifies this deliberate difference. The issue keeps future explicit policies open. |
| Refer To, Stop at Grid, and Pixel Connectivity are Tool preferences. `NEVER=0`, `ALWAYS=2`; `IF_VISIBLE=1` depends on GUI state. | Set matching preferences for both native tools and restore them. Public input has an explicit boolean Grid policy. Perturbed-preference tests cover success and failure. |
| Freehand Algorithm values are Regular 0, Pixel-perfect 1, Dots 2 (`src/app/tools/freehand_algorithm.h`). Dots is not promised by the 1.3.18.5 public scripting documentation. | Verify each algorithm independently. Ordered, reversed, repeated, one-point, corner, and straight gestures are compared with direct native calls. A straight Dots gesture marks its endpoints instead of promising every interpolated pixel. |
| `app.useTool` consumes the points as one press/move/release sequence (`src/app/script/app_object.cpp`). | Pass one dense ordered sequence. Do not resample or normalize it. Results retain exact order and multiplicity. |
| Eraser uses left-button erasure and right-button `replace_fg_with_bg` (`data/gui.xml`). Background erasure consumes the editor background-color preference, not only the supplied `bgColor` argument. | Keep explicit discriminated behaviors. Set and restore `app.bgColor` for the native call. Test both behaviors in RGB, Grayscale, and Indexed, on Transparent and Background Layers. |
| Native effect Inks have distinct opacity semantics. For example, RGB alpha erasure at opacity 128 leaves alpha 127; Indexed erasure need not have that result. | Report requested opacity as Eraser's effective opacity and preserve native pixels. Fill/Pencil retain the #26 `simple` and `copy-color` effective-opacity rule. Test 0, 128, and 255 instead of adding a blending algorithm. |

## Durable verification

- `tests/paint/test_e2e_fill_paint.py` and `fixtures/fill_paint_reference.lua`:
  independent native matching and pixel oracle for source scope, addressed Frame,
  hidden Layers, Color Modes, connectivity, non-contiguous matching, tolerance,
  Grid, Ink/opacity, no-op coverage, Backgrounds, links, clipping, and Selection.
- `tests/paint/test_e2e_freehand_paint.py` and
  `fixtures/freehand_paint_reference.lua`: direct native gesture comparison for
  algorithms, Point order/multiplicity, Ink/opacity, both Eraser behaviors,
  Backgrounds, links, clipping, and Selection.
- `tests/paint/test_e2e_native_paint.py` and
  `fixtures/native_paint_isolation.lua`: editor-state restoration after success,
  native-call failure, bounds refusal, and save failure for all eight fixed Tool
  spellings, including the previously delivered Line and Shape tools.
- `tests/paint/test_e2e_paint_tools.py`: public CLI tracer cases through saved and
  reopened assets. Unit tests check request/schema agreement and independent
  algorithm Capability Gaps; runtime and package tests check installed resources.

The reference fixtures do not call SPA's Paint implementation. They compare public
results with native Tools and independently decode saved output through Image Get.
Coverage is distinct from changed pixels. Failure cases preserve Source bytes and
do not publish a Target. Exact test counts and the reviewed commit belong to the PR
validation report.

These observations do not add a public Tool wrapper, alternate rasterizer,
Paint Dynamics simulation, or a new runtime support registry.
