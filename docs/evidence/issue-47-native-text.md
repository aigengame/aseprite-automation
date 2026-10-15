# Native text rasterization maintenance note

SPA does not provide text rasterization. Raster Authoring owns the Capability Gap
reason, and discovery projects it without registering a text Descriptor, schema,
command, or Plan Step. The public reason directs callers to external rasterization
and Raster Import.

The Baseline Aseprite definition is `SPA_BASELINE_ASEPRITE_VESION` in
`src/spa/__init__.py`. It is a maintenance reference, not a compatibility guarantee.

## Implementation reason

The native text paths depend on editor font and theme owners. `PasteText` reads
font preferences before applying non-UI font parameters; absent font/theme state
can cause a process failure or leave the Image unchanged. `GraphicsContext` text
drawing and measurement also require the theme's font state. Command completion
alone therefore does not establish text output or persistence.

Discovery does not invoke these text paths. This boundary does not assert a permanent
Aseprite limitation or behavior on every platform or release. A future accepted text
Operation requires an explicit contract and verified native output.

Relevant native source files are `src/app/commands/cmd_paste_text.cpp`,
`src/app/fonts/font_info.cpp`, `src/app/util/render_text.cpp`, and
`src/app/script/graphics_context.cpp`.

## Existing checks

- `tests/paint/test_e2e_text_discovery.py` checks installed `info` and `schema`,
  the public reason, selected runtime identity, and the absence of callable text.
- `tests/paint/test_integration_text_discovery.py` checks that the Gap describes
  SPA's boundary independently of selected-version identity and preserves usable Paint.
- `tests/paint/fixtures/native_text_probe.lua` is a manual investigation fixture.
  It seeds font preferences, measures pixels, and checks save/reopen with a rectangle
  control. It is not called by pytest or production discovery and does not repeat
  the unsafe fresh-preference path.

Use `SPA_TEST_ASEPRITE` as described in [Testing](../testing.md). For an installed
wheel check, `SPA_TEST_INSTALLED_CLI` selects that installation's `spa` executable.
