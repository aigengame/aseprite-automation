# Issue #37: native Color Curve and Replace Color

## Scope and authority

Issue #37 owns the feature scope. ADR-0074 owns shared Filter semantics. Tests use
macOS Aseprite 1.3.18.5 and the installed SPA CLI. Direct-command fixtures call
Aseprite without importing SPA's parameter mapping or an alternative color formula.
Linux validation is reported separately in the PR when available.

The current delivery covers ordinary Image Layer pixels in RGB, Grayscale, and
Indexed documents. Both operations refuse resolved Tilemap pixel targets, including
mixed requests and `all`; unrelated Tilemaps remain intact. Neither operation has
Palette mutation, Tiled Mode, or Operation Plan admission. These are current scope
choices, not permanent restrictions on later accepted requirements.

## Public examples

`spa filter color-curve --input-json` accepts:

```json
{
  "source_sprite_file": "source.aseprite",
  "target_sprite_file": "curved.aseprite",
  "in_place": false,
  "overwrite": false,
  "color_mode": "rgb",
  "channels": {"kind": "components", "names": ["red"]},
  "cels_target": {"kind": "all"},
  "points": [{"input": 100, "output": 42}]
}
```

One point gives a native constant curve. One to 256 integer control points are
allowed, with input and output in 0..255. Inputs must strictly increase; SPA does
not sort them. Aseprite extends omitted endpoints and interpolates linearly.

`spa filter replace-color --input-json` accepts:

```json
{
  "source_sprite_file": "source.aseprite",
  "target_sprite_file": "replaced.aseprite",
  "in_place": false,
  "overwrite": false,
  "color_mode": "indexed",
  "palette_frame_number": 1,
  "channels": {"kind": "index"},
  "cels_target": {"kind": "all"},
  "from": {"kind": "palette-index", "index": 1},
  "to": {"kind": "palette-index", "index": 2},
  "tolerance": 0
}
```

RGB uses RGBA Color Values and selected RGBA components. Grayscale uses Grayscale
Color Values and gray/alpha components. Indexed uses PaletteIndex Color Values in
both the exclusive `index` and RGBA `components` Channel modes. From/To indexes
must exist in the requested Effective Palette. Palette Frame is one-based; indexes
are zero-based. Tolerance is an explicit integer in 0..255.

Native matching requires every selected component to be within tolerance; unselected
components do not constrain matching and are not replaced at that stage. Indexed
components then pass through native Palette/RGB Map projection, which can change
unselected resolved components. Index mode compares stored index distance.

## Discriminating observations

- A Red-only constant curve maps `(100,60,20,255)` to `(42,60,20,255)`.
- Curve identity, descending, and nonmonotonic paths match direct Aseprite commands
  in RGB, Grayscale, Indexed components, and stored Index mode. The native Index
  curve clamps its output to the Palette's valid entry range.
- With Red-only selection, `from.red == to.red == 100` and tolerance 60 changes the
  source Reds `[100,200,40]` to `[100,200,100]`. `changed_pixel_count` is 1, despite
  the two matching pixels. No match count is claimed.
- Replace Color count compares stored pixel values per distinct original target
  Image. It aligns old/new pixels by Canvas coordinates over the union of old and new bounds, and reads
  an absent pixel as the native transparent value. Linked consumers count once.
  Digest/bounds/survival facts separately establish the complete `changed` result.
- Transparent-to-visible replacement expands a 1x1 Cel at Canvas x=1 to a 4x1
  Cel at x=0. The original opaque pixel stays unchanged; three added visible
  pixels produce `changed_pixel_count=3`. The same count applies when another
  Frame links the Image. This regression catches old-area-only counting and its
  corresponding validation cap.
- Alpha can trim transparent edges or delete a Cel and its linked occurrences.
  Results report nullable Image digests and Cel bounds. Source bytes are preserved.
- Background Alpha is rejected before mutation because native execution masks it.
- Empty Selection preserves pixels. Explicit Selection uses Canvas coordinates.
- Indexed Palette basis is installed as the native active Frame independently of
  target Frame selection. Neither operation changes Palette state.
- Real fault injection confirms native transaction rollback and restoration of
  active Sprite/Layer/Frame, ranges, Palette picks, and Selection after failure.

The native source at `375989a61c3425cd4e8cdedfcfcca4bdfef7e1d9` explains these
observations: `src/filters/color_curve.cpp`, `color_curve_filter.cpp`, and
`replace_color_filter.cpp`; `src/app/commands/new_params.cpp` maps Lua points/colors;
`filter_manager_impl.cpp` chooses the active Frame's Palette/RGB Map and deduplicates
Image IDs; native `PatchCel`/`TrimCel` owns writeback. This evidence profile does not
promise a range of Aseprite releases. Independent runtime gates must pass on the
selected runtime before advertising either Operation.

## Reproduction

Run the focused real suite with a configured `SPA_TEST_ASEPRITE`:

```sh
uv run --frozen --group test pytest tests/filter/test_e2e_color_curve.py \
  tests/filter/test_e2e_replace_color.py tests/filter/test_e2e_pixel_filters.py \
  tests/filter/test_e2e_filter_state.py -x -vv --tb=short
```

Request/schema tests and malformed-evidence publication tests run in the ordinary
`not e2e` suite. No full example reconstruction or workflow change is required.
