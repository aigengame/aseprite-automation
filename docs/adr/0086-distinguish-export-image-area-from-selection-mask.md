# ADR-0086: Distinguish Export Image Area from Selection Mask

## Status

Accepted

## Context

The initial Command Catalog described `spa export image` as exporting a still Frame,
Layer composition, or Selection. That wording conflates two different Aseprite
concepts.

`SaveFileCopyAs.bounds` accepts one Canvas Rectangle and exports that rectangular
portion of the rendered image. The editor's Selected Canvas path obtains the current
Selection bounds and passes that Rectangle. Neither path applies the non-rectangular
Selection Mask to the exported pixels.

A real Aseprite 1.3.18.5 headless probe made the distinction visible. A 3-by-3 Sprite
contained selected pixels only at opposite corners and an unselected opaque red
center pixel. The Selection bounds covered the full canvas. Exporting with those
bounds preserved the red center pixel, proving that the native operation cropped to
the bounding Rectangle rather than masking pixel content.

SPA already defines Selection as a canonical binary Mask value. Calling a rectangular
crop a Selection export would make that contract false and would prevent a later
true masked export from receiving explicit outside-mask semantics.

## Decision

- `spa export image` uses a required discriminated Export Image Area:
  - `canvas` exports the complete Sprite canvas;
  - `bounds` exports one explicit positive Rectangle in Canvas Pixel space;
  - `slice` resolves one exactly addressed Slice and the effective Slice Key at the
    selected Frame, then exports that Key's Bounds.
- Exactly one Area variant is present. The Result reports the requested variant, the
  resolved Canvas Rectangle, and, for `slice`, the Slice address, Key Frame Number,
  and effective Frame Range.
- Normal coordinate, target-resolution, and runtime capability rules apply. The
  concrete `export image` vertical slice must prove and document native behavior for
  out-of-canvas Bounds before publishing that input territory; it cannot silently
  clamp, pad, or reinterpret the Rectangle.
- Export Image Area accepts no Selection or Selection Encoding. In particular, SPA
  does not derive a Rectangle from `Selection.bounds` and then claim that the Mask
  was applied.
- The Command Catalog describes this capability as exporting a Canvas, Bounds, or
  Slice area rather than exporting a Selection.
- A future workflow may justify true Selection-masked image export. That capability
  must reuse the canonical Selection Encoding and explicitly define the pixels
  outside the Mask, including transparency or fill behavior, Color Mode and
  Background handling, output bounds, and verification. It cannot be implemented by
  passing only the native bounding Rectangle.
- The fixed Lua Kernel owns native Area resolution and export invocation. Python
  does not rasterize or apply a Selection Mask.

## Consequences

- `export image` names the behavior Aseprite actually provides through the supported
  non-interactive seam.
- Agents cannot mistake a non-rectangular Selection for a pixel mask that the export
  operation silently ignores.
- Slice export retains Aseprite's timeline-aware Slice Key semantics instead of
  flattening a Slice to one timeless Rectangle.
- True masked export remains available as a future functional capability with an
  explicit contract rather than being prohibited or accidentally approximated.

## Rejected alternatives

### Treat Selection bounds as Selection export

The real probe preserved an unselected pixel inside the bounding Rectangle. Naming
that behavior Selection export would contradict the canonical Selection Encoding.

### Apply a Selection Mask in Python

That would move core pixel and Color Mode behavior out of the Lua Kernel and create
a second raster authority.

### Exclude future masked export

SPA's capability should deepen when agent workflows need it. The correct response is
to define its functional semantics explicitly, not to impose a permanent product
restriction.
