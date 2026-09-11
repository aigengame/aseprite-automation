# ADR-0025: Preserve Aseprite geometry and declare Coordinate Spaces

## Status

Accepted

Feature issues own operation-specific bounds and acceptance.

## Context

Aseprite uses Point and Rectangle values across Sprite, Image, Cel, Selection,
Slice, and Tile operations. SPA also works with distinct Canvas Pixel, Image
Pixel, Tile Cell, and Tile Bitmap Pixel spaces. Endpoint aliases and global
position rules would obscure which pixels are covered and would reject valid
native structures such as an off-canvas Cel.

## Decision

- A public Point contains integer `x` and `y` coordinates with a zero-based
  top-left origin in its declared Coordinate Space.
- A public Rectangle contains integer `x` and `y` plus non-negative integer
  `width` and `height`. It covers the half-open region from its origin to,
  but not including, `x + width` and `y + height`.
- A zero width or height is a valid empty Rectangle observation. An Operation
  that must modify pixels requires a non-empty region.
- Every coordinate-bearing Operation declares its Coordinate Space. Values from
  different spaces are not interchangeable.
- Negative positions are not rejected globally; the owning Operation applies
  the native object's rules.
- Raster writes reject out-of-bounds Rectangles unless an Operation explicitly
  supports and the caller selects clipping. A clipped result reports the
  applied Rectangle.

These are shared value semantics, not a general spatial framework. Domain
modules own their transforms, bounds, and result facts.

## Consequences

Coordinates have one coverage convention while native off-canvas structures
remain representable. An explicit clipping choice prevents a partial edit from
appearing complete.

## Rejected alternatives

Publishing both dimensions and endpoint aliases creates off-by-one ambiguity.
Silent clipping hides unapplied pixels. Rejecting all negative positions
contradicts valid Aseprite documents.
