# Issue #25 — Native Paint Composite evidence

## Native profile

Probes ran on macOS on 2026-09-29 with Aseprite `1.3.18.5-dev`, API 41, Lua 5.4.
Executable SHA-256:
`724f4cc88566c9d63013d1e9cca31d34ee7f9e12497ec07ae930aa6cafe63b7c`.
The reference Aseprite source is commit
`375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9`; that is not a verified executable build
commit. Invocations used SPA's isolated runtime preparation. Linux verification
remains unavailable because the GitHub Actions quota is exhausted.

## Native facts

- `Image:drawImage` reads opacity only when `lua_isinteger` succeeds. JSON-decoded
  numeric values need explicit integer conversion before this native call, or the
  native default is 255. The fixed helper converts the validated value.
- Over an alpha-zero RGB destination, native Normal can retain source RGB even at
  opacity zero while the resulting alpha stays zero. SPA preserves those native
  stored values; changed-pixel counts describe stored values, not visual difference.
- Grayscale HUE, SATURATION, COLOR, and LUMINOSITY select Normal. Grayscale ADDITION
  selects Exclusion in `Image:drawImage`'s new-blend path. These five combinations
  have typed refusals and Capability Gaps instead of successful substituted effects.
- `HSL_HUE`, `HSL_SATURATION`, `HSL_COLOR`, and `HSL_LUMINOSITY` are valid compatibility
  aliases. The implementation and oracle use the current HUE/SATURATION/COLOR/LUMINOSITY
  names. The alias spelling is not a native behavior defect.

Source anchors:
[Image binding](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/script/image_class.cpp#L318),
[blenders](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/doc/blend_funcs.cpp#L817),
[Lua enum aliases](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/app/script/engine.cpp#L315).

## Indexed prerequisite experiment

A 1×1 Indexed target at Frame 2 used transparent index 7. Its first Palette had
eight entries; the Frame 2 Palette Change had nine. Source index 8 was valid only
in Frame 2's Effective Palette. Direct Cel-associated `drawImage` kept destination
index 1 because the binding selected Palette 0. An isolated temporary Indexed Sprite
with the Frame 2 Palette wrote index 8 and preserved the transparent-index behavior.
The original Palette entries, active Sprite/Layer/Frame, and Source file bytes were
restored or unchanged after the successful probe.

All 19 modes at opacity 0, 1, 127, and 255 selected the same source index. Thus the
temporary Sprite corrects the Palette basis, but cannot add color blending or
opacity semantics. Native Indexed-to-Indexed composition is index selection, with
source-mask and Palette-size checks; it does not quantize RGBA blend results.
See the [native branch](https://github.com/aseprite/aseprite/blob/375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9/src/doc/blend_internals.h#L200).
This prototype alone was not production Indexed delivery or failure-cleanup evidence.
The owner accepted Normal/255 native index overlay on 2026-09-29. Other Indexed
combinations remain typed gaps; SPA does not emulate RGBA blending or conversion.
The production helper binds the addressed Frame's Palette to a temporary Sprite,
draws once through its associated Cel, copies the result, closes the Sprite, and
restores active Sprite/Layer/Frame. A separate capability probe observes both a
missing-index and present-index Palette plus the nonzero transparent index.

## Executable verification

Review reproduced a JSON/Lua precision loss with `position.x=9007199254740993`:
the returned position differed from the request and publication was refused. The
owner accepted signed 32-bit position coordinates, matching native Point, on
2026-09-29. The request schema now rejects values outside that range before runtime
invocation. Both range endpoints still support explicit clipping with exact skipped
coverage; only the bounded intersection reaches native Point. This is an
operation-specific limit under ADR-0025, not a change to every Raster Point.

`tests/paint/fixtures/composite_modes.lua` generates a native oracle independently
of SPA's composite helper. It also checks a literal HUE sample so an enum alias to
Normal cannot silently make implementation and oracle agree on the wrong result.
`tests/paint/test_e2e_composite_modes.py` compares persisted public CLI output with
that oracle: RGB 19 modes × three opacities, Grayscale 14 modes × three opacities,
Background opacity, Linked Cels composited once, and explicit Canvas Selection.
The 102 cases passed in 73.27 seconds before the documentation checkpoint.

`tests/paint/test_e2e_composite.py` covers canonical inline/Artifact transport,
explicit opacity, coverage partitions, fully clipped large positions, native
mode refusals, invalid requests, and unchanged Source/existing Target on failure.
`tests/paint/test_unit_composite.py` checks public input constraints and rejection
of malformed Kernel evidence before publication. Existing Image replace tests
verify the shared Snapshot materializer against replacement semantics.

`tests/paint/test_e2e_composite_indexed.py` adds the public CLI tracer above,
Palette Changes, linked-frame Palette applicability, Background opacity, explicit
normal/255 restrictions, and atomic failures. Its native context probe also injects
an error after temporary Sprite creation to check cleanup and active-state restoration.
