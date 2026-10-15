# Native Paint Composite maintenance note

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. It is a maintenance reference, not a compatibility guarantee.

## Implementation reasons

- `Image:drawImage` reads opacity as a Lua integer. The helper converts the validated
  JSON value before invocation so native default opacity cannot replace it.
- Native Normal can preserve RGB values at alpha zero. Changed-pixel counts describe
  stored values, not visible difference; SPA does not normalize those values.
- Grayscale HUE, SATURATION, COLOR, and LUMINOSITY select Normal, while ADDITION
  selects Exclusion. SPA refuses these combinations and publishes feature-owned
  reasons that identify the restriction and a supported choice.
- Indexed composition uses native index selection, not RGBA blending. SPA admits
  only Normal at opacity 255. An isolated temporary Sprite binds the addressed
  Frame's Effective Palette; the helper closes it and restores active state after
  success or failure. Source and output indexes are checked against the applicable
  Palettes and Transparent Color Index.
- Position coordinates use signed 32-bit native Point bounds. Preflight rejects
  larger values before JSON/Lua precision loss can change the requested position.

Relevant native source files are `src/app/script/image_class.cpp`,
`src/doc/blend_funcs.cpp`, `src/doc/blend_internals.h`, and
`src/app/script/engine.cpp`. SPA uses the canonical Blend Mode enum names.

## Existing checks

- `tests/paint/fixtures/composite_modes.lua` supplies an independent native oracle
  and a literal HUE witness.
- `tests/paint/test_e2e_composite_modes.py` compares persisted CLI results for RGB
  and admitted Grayscale modes, opacity, Backgrounds, links, and Selection.
- `tests/paint/test_e2e_composite.py` covers transports, clipping, refusals, and
  unchanged Source/existing Target on failure.
- `tests/paint/test_unit_composite.py` checks input bounds and malformed native
  evidence before publication.
- `tests/paint/test_e2e_composite_indexed.py` checks Palette time, linked Frames,
  Transparent Color Index, Normal/255 admission, and temporary-state cleanup.

These checks support the current implementation. They do not establish identical
native pixels on every release or platform.
