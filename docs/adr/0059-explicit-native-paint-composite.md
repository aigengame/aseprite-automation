# ADR-0059: Make Paint Composite explicit and gate Indexed native delegation

## Status

Accepted

## Context

Exact Pixel Patch replacement and alpha/BlendMode composition are different editing
intents. Aseprite `Image:drawImage` supplies the native compositor, but its defaults
and coercions are unsuitable as an implicit agent contract: opacity is clamped,
several script BlendMode values are silently mapped to Normal, clipping is implicit,
and the Cel-associated Indexed path uses Palette 0.

SPA needs the full compositing capability with declared inputs and observable output.
It must not claim Palette-correct Indexed behavior before a native delegation route is
proven, nor maintain a second implementation of Aseprite's blend mathematics.

## Decision

- `spa paint composite` accepts a Pixel Region Snapshot inline or from the identical
  JSON Artifact schema. Its source Rectangle is rebased to `(0,0)` in a constructed
  source Image.
- An integer target Image Pixel `position` places that source origin.
- The request requires integer `opacity` in `0..255`. Values outside the range fail
  instead of being clamped.
- The request requires one supported Aseprite BlendMode: `normal`, `multiply`,
  `screen`, `overlay`, `darken`, `lighten`, `color-dodge`, `color-burn`, `hard-light`,
  `soft-light`, `difference`, `exclusion`, `hue`, `saturation`, `color`, `luminosity`,
  `addition`, `subtract`, or `divide`.
- Script BlendMode values that `Image:drawImage` silently maps to Normal are rejected
  rather than exposed with false semantics.
- Source and destination Color Modes must match. Cross-mode composition requires a
  separately declared operation-specific conversion before Composite.
- Clipping and optional Selection Application reuse `paint apply`: default `reject`,
  explicit `clip`, addressed-Cel Image-to-Canvas mapping, no current Selection, and
  complete applied/skipped observations.
- Existing ordinary Image and Background Cels are supported, and Background output
  must satisfy its native opaque postcondition. Reference, Tilemap, absent, and
  non-Cel targets fail.
- A linked Image is composited once and native sharing remains intact.
- RGB and Grayscale composition delegates to native `Image:drawImage` through the
  fixed Lua Kernel handler.
- Indexed composition requires `palette_frame_number`. It must resolve to the
  addressed target Cel Frame's Effective Palette and declares the palette used to
  interpret source/destination indexes and quantize output.
- Aseprite 1.3.18.5's Cel-associated path uses Palette 0. Indexed delivery therefore
  requires a real-runtime vertical slice proving a Palette-correct native delegation
  route, such as an isolated temporary Sprite or temporary Palette substitution with
  complete restoration and transactional rollback.
- Until that route is proven, `spa info` reports the Indexed Composite Capability Gap
  and the operation returns a typed refusal for Indexed input. Indexed remains part
  of the intended product capability.
- SPA does not fall back to Palette 0 and does not rewrite Aseprite BlendMode math in
  Lua or Python. The Lua Kernel remains the public semantic authority and delegates
  pixel composition to the native implementation.
- Validation, native composition, Selection application, Background postcondition,
  and commit execute as one all-or-nothing Mutation.
- Results return source, target, and applied Rectangles; clipped and Selection
  coverage; opacity; BlendMode; optional Composite Palette Basis; changed/skipped
  pixel counts; every affected Cel/link; unchanged geometry; and before/after content
  digest. Save/close/reopen verifies persisted facts.

## Consequences

- Exact replacement and native composition remain independently understandable.
- Agents cannot accidentally request a clamped opacity or silently downgraded mode.
- RGB and Grayscale retain native compositor behavior.
- Indexed stays on the product path without publishing known-wrong Palette semantics.

## Rejected alternatives

### Use every script BlendMode enum

Some enum values are silently converted to Normal by the Image compositing path.

### Accept Palette 0 for every Indexed target

It contradicts the target Frame's Effective Palette when Palette Changes exist.

### Reimplement all blend modes in Lua or Python

That duplicates complex Aseprite behavior and creates a long-term semantic fork.

### Remove Indexed from the product contract

The native integration gap is a delivery constraint, not a reason to reduce the
Raster authoring capability.
