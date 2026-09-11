# ADR-0050: Separate Tile Image and Cel position policies in Tileset Resize

## Status

Accepted

## Context

ADR-0049 defines Tileset Grid change as replacement-style `tileset resize`. A new
Grid changes two different things: every Tile's Bitmap dimensions and every
referencing Tilemap Cel's mapping from Tile Cell space to Canvas Pixel space. One
generic resize option would conflate pixel transformation with spatial placement.

Aseprite's native Sprite resize scales Tile Images and Cel positions together. A
Tileset-scoped Operation must not assume that the Sprite canvas or every authored
position should also scale. Agents need explicit policies that compose with the
shared Raster Authoring semantics and retain the logical Tilemap Cells.

## Decision

- `tileset resize` requires one Tile Image Transform:
  - `scale` resizes every non-empty Tile Image to the target Grid dimensions through
    the same interpolation and Color Policy semantics as `image resize`.
  - `canvas` preserves source pixels 1:1. It places the source Image's `(0,0)` at
    explicit `offset_x/offset_y` in target Tile Bitmap Pixel space, clips pixels
    outside the target bounds, and fills uncovered pixels with an explicit Color
    Value compatible with the Sprite Color Mode.
- Empty Tile is recreated through native Tileset construction. Every non-empty Tile
  retains its order, Tile Key, data, and all accepted Properties.
- `tileset resize` also requires one Tileset Resize Cel Position Policy:
  - `keep_canvas_position` retains every referencing Cel's Canvas Pixel position.
  - `preserve_grid_position` requires each Cel's X position to be exactly divisible
    by the old tile width and Y position by the old tile height. The resulting
    integral Grid coordinates are multiplied by the new dimensions. No rounding is
    performed; an unaligned Cel fails preflight before mutation.
- Both Cel policies preserve Tilemap Image width and height in Tile Cells, every Tile
  Placement meaning, and all X/Y/diagonal flags. They do not resample or clip a
  Tilemap Image.
- The new Tileset Grid uses Aseprite's fixed origin `(0,0)`.
- Internal Layer rebinding uses the accepted `by_key` Tile Rebinding Map and
  `use_target` Grid Policy.
- The Operation does not resize the Sprite canvas. Canvas coverage outside the
  Sprite remains authored content and is reported rather than clipped or discarded.
- Results return every Tile Image transform, old and new Tile dimensions, all old and
  new Cel positions, effective Grids and Canvas coverage, and final
  Tileset/Tile/Placement facts.
- `scale` depends on the shared Image Resize interpolation and Indexed Color
  semantics. Issue #45 owns feature delivery and acceptance.

## Consequences

- Pixel transformation and Tilemap positioning can vary independently without
  ambiguous flags.
- `canvas` supports deterministic padding and cropping without resampling pixel art.
- `preserve_grid_position` preserves exact logical offsets from the fixed Grid
  origin and refuses lossy rounding.
- Existing Raster Authoring remains the authority for scaling and Color behavior.
- The operation preserves logical Tilemaps while making changed Canvas coverage
  observable.

## Rejected alternatives

### Scale Tile Images and Cel positions together unconditionally

That imports Sprite-wide resize intent into a Tileset-scoped Operation.

### Add crop, pad, and anchor as separate transform modes

One explicitly offset `canvas` copy represents all three without duplicate geometry
rules.

### Round unaligned Cel positions

Different rounding choices move authored content. The caller can first reposition a
Cel explicitly or choose `keep_canvas_position`.

### Resize Tilemap Cell arrays with the Tile Bitmap

Tile Cells and Tile Bitmap Pixels are different coordinate spaces. Changing Tile
Bitmap size does not imply changing the logical map dimensions.

### Clip resulting coverage to the Sprite canvas

Off-canvas Cel content is valid Aseprite state and must not be discarded implicitly.
