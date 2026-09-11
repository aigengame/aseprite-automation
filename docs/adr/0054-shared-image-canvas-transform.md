# ADR-0054: Share one Image Canvas Transform across Images and Tiles

## Status

Accepted

## Context

SPA needs a Raster operation that can enlarge, crop, pad, or reposition an Image
buffer without scaling its pixels. Tileset Resize already needs the same copy/fill
algorithm for each Tile Bitmap. Implementing these paths separately would create two
authorities for offsets, clipping, fill, and Color Mode behavior.

Aseprite's editor-level Canvas Size applies to a Sprite. This decision instead scopes
the public command through the `image` command domain and keeps Sprite Canvas Size as
a distinct Sprite-level operation.

## Decision

- Image Canvas Transform is a pure Raster Authoring transform owned by the fixed Lua
  Kernel. `image canvas-resize` and Tileset Resize `canvas` call the same handler.
- It requires exact positive integer target `width/height`, integer
  `offset_x/offset_y`, and an explicit Color Value compatible with the source Pixel
  Format and applicable Palette facts.
- The offset places source Image Pixel `(0,0)` at that coordinate in target Image
  Pixel space.
- The Kernel creates and fills a same-Pixel-Format target Image, then copies each
  intersecting source pixel 1:1 through the offset. Source pixels outside the target
  are discarded and uncovered target pixels retain the declared fill.
- A request with no source/target intersection remains valid and produces the
  explicitly requested fill-only Image. No additional overlap guard is introduced.
- The transform does not scale pixels, center content, change Color Mode,
  resize the Sprite canvas, or apply a Selection.
- `spa image canvas-resize` applies to an existing Cel on an ordinary transparent
  Image Layer and requires one Image Canvas Cel Position Policy:
  - `keep_cel_position` leaves every affected Cel position unchanged, so copied
    source pixels move on the Sprite Canvas by the transform offset.
  - `preserve_source_canvas` subtracts the transform offset from every affected Cel
    position, preserving the Canvas coordinates of every copied source pixel.
- A linked Image is transformed once. The same position delta applies to every Cel
  sharing it and native links remain intact. Isolated behavior requires `cel unlink`
  first.
- Tilemap, Background, Reference, absent, and non-Cel targets are rejected by the
  public Image operation. Tileset Resize invokes only the pure transform on Tile
  Bitmaps in Tile Bitmap Pixel space.
- Buffer replacement and all Cel position changes execute as one all-or-nothing
  Mutation.
- Results return requested and actual dimensions, offset, fill, copied and discarded
  source Rectangles, uncovered target region, Pixel Format, every affected Cel/link
  and old/new position, and before/after content digest. Save/close/reopen verifies
  the persisted result.
- Python orchestration and Tileset-specific Lua code may invoke this handler but may
  not recreate its copy, clipping, fill, or offset semantics.

## Consequences

- Crop, padding, and buffer repositioning have one explicit non-scaling operation.
- Image and Tile workflows cannot drift into different pixel-copy behavior.
- Cel placement remains separate from the reusable buffer transform.
- A fully discarded source is explicit input behavior rather than a hidden safety
  subsystem.

## Rejected alternatives

### Extend `image crop` beyond source bounds

That would overload strict crop with target construction and fill semantics.

### Reuse Aseprite Sprite Canvas Size directly

It operates on the whole Sprite and its Cels, not one linked Image buffer.

### Implement Tile canvas resizing separately

That violates the Lua Kernel's DRY authority over core operation semantics.

### Require a non-empty copied intersection

The exact size, offset, and fill already define a deterministic fill-only result; an
extra guard would add policy without adding image-editing capability.
