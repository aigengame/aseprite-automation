# ADR-0061: Define Standard Paint Brush and native Paint Line

## Status

Accepted

## Context

Aseprite's Line tool paints with a Brush. Brush size is not an independent stroke
width, and `BrushType.LINE` names an oriented Brush footprint rather than the Line
tool. Aseprite clamps invalid Brush sizes and tool opacity, while omitted Brush and
tool fields can read active editor state.

Image Brush and Shading Ink add native mask, pattern, color-replacement, and Shade
configuration that must be made explicit before they are deterministic agent inputs.

## Decision

- Standard Paint Brush is the shared typed value for Aseprite Brush types `circle`,
  `square`, and `line`.
- It requires positive integer `size`. Non-positive input fails instead of inheriting
  Aseprite's clamp to 1.
- Circle uses fixed angle 0 and rejects an angle field.
- Square and Line require integer `angle` from `-180` through `180`.
- A Line Brush is an oriented footprint stamped by a Paint tool; it does not name the
  Line tool.
- Image Brush is a distinct intended capability whose mask, center, pattern,
  pattern-origin, and color-replacement semantics receive a separate contract and
  real-runtime gate.
- `spa paint line` fixes Native Tool Invocation to Aseprite's Line tool.
- It requires exactly two Image Pixel Points, `from` and `to`. Equal Points invoke the
  native single-point stroke behavior.
- It also requires a Standard Paint Brush, compatible Color Value, integer `opacity`
  in `0..255`, and an Ink of `simple`, `alpha-compositing`, `copy-color`, or
  `lock-alpha`.
- Invalid opacity fails instead of being clamped. The Kernel supplies left button,
  exact Cel/Layer/Frame, Brush, color, Ink, opacity, and safe fixed values for other
  Native Tool Invocation options.
- Shading Ink remains an intended Paint capability. Until its complete Shade
  configuration can be supplied and restored explicitly, a request for it returns a
  typed Capability Gap and never reads editor Shade preferences.
- Paint bounds refusal, explicit clipping, and explicit Selection Application are
  evaluated against the native rendered Brush footprint rather than endpoint bounds.
- Native execution cannot create a Cel, expand its Image, move it, or break links.
- Existing ordinary Image and Background Cels are supported subject to the opaque
  Background postcondition. Reference, Tilemap, absent, and non-Cel targets fail.
- A linked Image is painted once and sharing remains intact.
- The all-or-nothing result returns endpoints, normalized Brush, Ink, opacity,
  requested and actual affected regions, clipped or Selection-excluded pixels,
  changed pixel count, every affected Cel/link, and before/after content digest.
  Save/close/reopen verifies persisted facts.

## Consequences

- Line requests describe the actual Aseprite Brush rather than an invented width.
- Native line rasterization remains authoritative across slopes and Brush footprints.
- Image Brush and Shading stay on the product path without inheriting hidden state.
- Line preserves the accepted Image, Cel, Selection, and Linked Image boundaries.

## Rejected alternatives

### Expose `stroke_width` without Brush semantics

Aseprite's Line tool stamps a Brush whose shape, size, and angle affect pixels.

### Treat Line Brush as the Line tool

They are separate native concepts and compose with each other.

### Accept native size or opacity clamps

The normalized request would otherwise differ from the caller's declared values.

### Read active Image Brush or Shade preferences

That would make identical agent requests depend on hidden editor state.
