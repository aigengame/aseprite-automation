# ADR-0052: Compose Image Resize with explicit Cel position policy

## Status

Accepted

## Context

ADR-0051 makes Image Resize Transform a pure Image-buffer semantic. Aseprite's
Cel-attached `Image:resize()` also accepts a pivot and changes the Cel position by
converting a scaled anchor calculation to integer coordinates. That behavior combines
two domain facts and inherits an implicit integer conversion.

SPA must retain pivot-based authoring while keeping the reusable buffer transform
independent for Tile Images. Linked Cels also require one coherent policy: changing
the shared Image dimensions affects the whole linked set, so pivot movement must not
silently isolate one Cel.

## Decision

- `spa image resize` applies to an existing Cel on an ordinary transparent Image
  Layer and composes Image Resize Transform with one required Image Resize Cel
  Position Policy.
- `keep` leaves every affected Cel's Canvas Pixel position unchanged.
- `pivot` accepts integer `pivot_x/pivot_y` in the old Image Pixel space. A pivot can
  be outside the old Image bounds because it is a transform anchor, not a pixel
  access.
- For each axis, `pivot` computes the exact rational position offset:
  `pivot - pivot * new_size / old_size`.
- `pivot` requires one Pivot Rounding applied independently to each rational offset:
  `toward-zero`, `floor`, `ceil`, or `nearest-away-from-zero`. No language or runtime
  default chooses the result.
- The Kernel rounds the offset once and applies that same integer offset to every Cel
  sharing the transformed Image. Native linked sharing is preserved. An isolated
  resize requires an explicit `cel unlink` first.
- Tilemap Cels are rejected because their Images contain Tile Cells. Background Cels
  are rejected because they must remain full-canvas. Reference Layers are rejected
  because their native resize behavior changes floating-point Cel bounds rather than
  an authored raster Image buffer.
- The Image replacement and every Cel position change execute in one all-or-nothing
  Mutation.
- Results include exact rational offsets, selected rounding, applied integer offsets,
  every affected Cel's old/new position, Image dimensions, sharing facts, and content
  evidence. Save/close/reopen verification confirms them.

## Consequences

- Image-buffer resize remains reusable by Raster and Tile Authoring.
- Pivot movement is available without hidden integer conversion.
- Linked Cels move coherently and stay linked.
- Layer kinds with different native invariants cannot be accidentally coerced into
  ordinary raster behavior.

## Rejected alternatives

### Put pivot inside Image Resize Transform

Tile Images and standalone Image buffers have no Cel Canvas position. Placement is
an outer Cel-targeted concern.

### Always keep the top-left position

That would omit Aseprite's useful pivot-based resize behavior.

### Inherit native integer conversion

Fractional anchor results need caller-visible rounding so agents can predict exact
Canvas positions.

### Move only the addressed Cel in a linked set

The Image resize affects every Cel sharing the Image. Isolated movement requires an
explicit unlink rather than hidden sharing changes.

### Apply Image resize to every Cel-bearing Layer kind

Tilemap, Background, and Reference Cels have distinct content or geometry invariants
and require their own Operations.
