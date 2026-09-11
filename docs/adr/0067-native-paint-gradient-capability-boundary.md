# ADR-0067: Preserve native Gradient semantics across a headless capability boundary

## Status

Accepted

## Context

Aseprite's Gradient tool combines ordered two-Point geometry, Gradient Ink, Linear or
Radial Gradient Type, an installed Dithering Matrix, opacity, and Flood Fill matching.
The first Point both starts the gradient axis and supplies the color-matching seed.

In Aseprite 1.3.18.5, `app.useTool` does not accept Gradient Type or Dithering Matrix.
The native Tool Loop reads both from GUI Context Bar methods whose source marks
non-UI support as TODO. Unlike Tool Preferences, no source-evident priming route can
supply them in headless execution.

## Decision

- Intended `spa paint gradient` invokes Aseprite's fixed `gradient` tool through
  Native Tool Invocation and declares `deterministic` Operation Determinism.
- It requires exactly two ordered Image Pixel Points, `from` and `to`. Their order
  defines foreground-to-background direction, and `from` is also the native Flood
  Fill seed.
- Equal Points retain the native Gradient result and are not converted into Paint
  Fill or a solid-color operation.
- The request requires compatible `foreground_color` and `background_color`, integer
  opacity in `0..255`, and Gradient Type `linear` or `radial`.
- Dithering Matrix is `none` or one uniquely resolved matrix name available in the
  installed Aseprite runtime. Missing or ambiguous names fail rather than falling
  back. Results report the resolved matrix identity and available matrix facts.
- Dithering Matrix is distinct from a color-conversion/export Dithering Algorithm and
  from Paint Dynamics.
- Paint Gradient reuses Paint Fill's tolerance, contiguous mode, applicable Pixel
  Connectivity, Refer To, and Stop at Grid semantics.
- Existing clipping, explicit Selection Application, target, Background, Linked
  Image, transaction, and postcondition rules apply.
- Indexed execution uses and reports the addressed target Frame's Effective Palette.
- Paint Gradient accepts no Brush, generic Ink, Freehand Algorithm, or seed. The
  fixed native tool selects Gradient Ink.
- A real Aseprite 1.3.18.5 headless negative probe must verify the source-indicated
  capability boundary and return a typed failure without hanging or corrupting the
  caller protocol.
- Until an explicit native headless route proves exact editor-pixel parity, complete
  option control, state restoration, atomicity, and persistence, the Surface Manifest
  omits Paint Gradient and `spa info` reports a version-specific Capability Gap.
- SPA does not substitute Paint Composite, GraphicsContext, Python, or a custom Lua
  Gradient renderer.

## Consequences

- The intended contract preserves the complete native Gradient capability rather
  than shipping a Linear/no-dither technical subset.
- Agents can distinguish an unavailable automation seam from a missing product
  requirement.
- Installed Dithering Matrix availability is explicit and inspectable.
- A later Aseprite API improvement can satisfy the existing contract without changing
  Gradient meaning.

## Rejected alternatives

### Use GUI Context Bar state implicitly

It is absent in headless execution and would make identical requests state-dependent.

### Publish a partial Gradient command

Omitting Radial or Dithering Matrix would present an adapter limitation as product
semantics.

### Render a gradient through Pixel Patch or Paint Composite

That would create a second authority instead of invoking Aseprite's Gradient tool.

### Drive the editor GUI

SPA automates Aseprite's non-interactive capabilities and does not reproduce editor
interaction.
