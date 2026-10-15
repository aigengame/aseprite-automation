# Despeckle and Convolution maintenance note

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. It is a maintenance reference, not a compatibility guarantee.

ADR-0074 owns shared Filter semantics. Despeckle is callable for ordinary Image
Layers. Convolution remains discovery-only with no callable Descriptor.

## Convolution

Runtime Integration scans bounded declaration metadata at the prepared invocation's
native resource paths. It follows native ResourceFinder ordering for user, generated,
and default files. Coefficients, divisor, and bias remain opaque; an incomplete scan
does not establish callability. This is not a resource registry or convolution engine.

Internal Runtime Observations retain requested/observed Channel comparisons. In
Baseline Aseprite, the native command does not apply its requested Channels to the
Filter manager, and an unknown resource can complete without an effect. Resource
defaults and command completion therefore cannot establish a faithful execution
contract. Raster Authoring owns the public reason that SPA does not provide
Convolution execution. Public discovery does not expose probe payloads.

Relevant source files under `src/app/` are `convolution_matrix_stock.cpp`,
`commands/filters/cmd_convolution_matrix.cpp`, `resource_finder.cpp`, and `filetoks.cpp`.

## Despeckle

The request uses integer window dimensions in `1..100`, including even windows.
Native sampling owns the anchor `floor(width/2), floor(height/2)` and upper median
`floor(width*height/2)`. SPA does not implement a median algorithm.

Indexed component Channels must include Green. In Baseline Aseprite, the preserved-
Green branch uses a packed RGBA value as a Palette index. SPA refuses that branch
without adding Channels or changing the requested interpretation. Index Channels
remain a separate supported choice.

A 1×1 window still invokes native Despeckle: component processing can remap duplicate
Palette colors to a different stored Index. Palette Entries remain unchanged.
Tilemap pixel targets and Background Alpha are refused before mutation. Explicit
Selection limits writes, linked Images are processed once, and save/reopen verifies
Images, Cel geometry, and Palette facts before Target Commit.

`none` disables wrapping and does not promise ideal edge repetition. The native
non-wrapped X loop can advance its coordinate before its pixel address catches up,
so wide windows can differ from ideal clamping. SPA preserves native output.
Relevant source files are `src/app/commands/filters/cmd_despeckle.cpp`,
`src/filters/median_filter.cpp`, and `src/filters/neighboring_pixels.h`.

## Existing checks

- `tests/runtime/test_unit_convolution.py` checks declaration scanning, platform
  paths, duplicates, defaults, and incomplete input.
- `tests/runtime/test_e2e_convolution.py` checks internal observations and the public
  Gap reason without asserting a callable Convolution Operation.
- `tests/filter/test_unit_despeckle.py` checks strict request/schema agreement.
- `tests/filter/test_integration_despeckle.py` checks returned native evidence before
  Target Commit.
- `tests/filter/test_e2e_despeckle.py` compares independent native commands and reopened
  output for Channel sets, window bounds, tiled edges, 1×1 behavior, Selection,
  links, and refusals. Its wide-window witness distinguishes native sampling from
  ideal clamping.
- `tests/filter/test_e2e_filter_state.py` verifies transaction rollback and editor-state
  restoration after an injected native failure.

For a manual windowed comparison, use `tests/filter/fixtures/despeckle_source.lua`
and `tests/filter/fixtures/despeckle_windowed.lua` with the same explicit request as
SPA. Compare reopened Images, geometry, and Palettes through
`tests/filter/support.py:observe_images`. Record the actual host and runtime for
that run; a local editor check does not establish Linux or automated CI coverage.

Run the focused automated checks with:

```sh
uv run --frozen --group test pytest tests/filter tests/runtime/test_e2e_convolution.py
uv run --frozen --group test pytest tests/runtime/test_unit_convolution.py
```

Set `SPA_TEST_ASEPRITE` as described in [Testing](../testing.md).
