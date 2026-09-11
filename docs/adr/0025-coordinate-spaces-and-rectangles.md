# ADR-0025: Preserve Aseprite geometry and declare Coordinate Spaces

## Status

Accepted

## Context

Aseprite exposes Point and Rectangle values throughout Sprite, Image, Cel,
Selection, Slice, and tile operations. Its Rectangle shape is `x`, `y`, `width`, and
`height`, with a top-left zero origin; zero width or height represents an empty
Rectangle. SPA also works with several incompatible domains: Canvas Pixels, Image
Pixels, Tile Cells, and pixels inside a Tile bitmap.

An agent must know both the coordinate space and exact covered cells or pixels.
Alternative endpoint fields such as `right`, `bottom`, `x2`, or `y2` create
inclusive-versus-exclusive ambiguity. A global prohibition on negative positions
would also contradict native behavior such as a Cel positioned partly outside the
Sprite canvas.

## Decision

- Public Point values contain integer `x` and `y` fields whose origin is zero-based
  at the top left of their declared Coordinate Space.
- Public Rectangle values contain integer `x` and `y` and non-negative integer
  `width` and `height` fields. SPA does not add endpoint aliases.
- A Rectangle covers the half-open region `x <= px < x + width` and
  `y <= py < y + height`.
- A Rectangle is empty when either dimension is zero. Read results can represent an
  empty Rectangle; an Operation that must modify pixels requires a non-empty region.
- Every coordinate-bearing Operation declares its Coordinate Space through typed
  fields or schema metadata. Values from Canvas Pixel, Image Pixel, Tile Cell, and
  Tile Bitmap Pixel spaces are not substituted for one another.
- Negative `x` or `y` is not rejected globally. Each Operation follows the native
  meaning of its object and space; for example, a Cel position can be off-canvas.
- A raster write rejects a Rectangle outside its target Image bounds unless that
  Operation explicitly supports and the caller selects clipping. A clipped success
  returns the actual applied Rectangle.

These rules are shared value semantics, not a general spatial framework. Domain
modules retain ownership of operation-specific bounds, transforms, and results.

## Consequences

- Rectangle dimensions and endpoint behavior remain consistent across public
  commands.
- Agents can distinguish a valid empty observation from a write that did nothing.
- Off-canvas native document structures remain representable without making raster
  writes silently lossy.
- Tests cover origins, exact upper boundaries, empty dimensions, negative positions
  where supported, incompatible Coordinate Spaces, rejection, and explicit clipping.

## Rejected alternatives

### Publish inclusive right and bottom coordinates

This duplicates width and height and invites off-by-one disagreement between fields.

### Silently clip every raster write

An agent could believe the whole requested edit was applied. Clipping is useful only
when it is explicit and its actual result is observable.

### Reject every negative coordinate

Some Aseprite objects, including Cels, can validly extend beyond the Sprite canvas.
The owning Operation must decide validity from its native semantics.
