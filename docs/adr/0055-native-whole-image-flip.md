# ADR-0055: Use native whole-Image flip with an explicit axis

## Status

Accepted

## Context

Aseprite 1.3.18.5 exposes `Image:flip(FlipType)`. It mirrors an Image in place,
defaults to horizontal when the argument is omitted, keeps the Image dimensions, and
does not change Cel placement. Its implementation does not restrict the containing
Layer kind.

SPA needs deterministic agent input, correct Linked Image behavior, and a clear
boundary between whole-Image transformation and Selection or Tilemap operations.

## Decision

- `spa image flip` targets the complete Image of one existing Cel.
- The request requires one axis matching Aseprite vocabulary:
  - `horizontal` mirrors left and right.
  - `vertical` mirrors top and bottom.
- SPA rejects an omitted or unknown axis instead of inheriting Aseprite's default.
- The fixed Lua Kernel handler resolves the complete linked set and invokes native
  `Image:flip` once for the unique Image. Aseprite owns the pixel-mirror execution;
  the Kernel owns SPA applicability, atomicity, observation, and result semantics.
- Existing Cels on ordinary Image, Background, and Reference Layers are supported.
  Background dimensions, position, and full-canvas invariants remain unchanged.
  Reference floating-point bounds remain unchanged.
- Tilemap Cels are rejected. Mirroring a Tilemap must be defined in Tile Cell and
  Placement terms rather than by treating packed Placement values as ordinary pixels.
- The whole Image is flipped. Current Selection state is neither read nor applied.
- Cel positions and Image dimensions remain unchanged. Every Cel sharing the Image
  remains linked and observes the same single transformation.
- The Mutation is all-or-nothing. Results return the explicit axis, dimensions,
  Layer kind, every affected Cel/link, unchanged position or Reference-bound facts,
  and before/after content digest. Save/close/reopen verifies the persisted facts.
- Python and alternate Lua paths may not implement another pixel-mirror algorithm.

## Consequences

- The command follows native Aseprite flip vocabulary and pixel behavior.
- Agents cannot accidentally select a default axis through omission.
- Background and Reference Images retain their native geometry invariants.
- Selection-aware and Tilemap-aware mirrors remain distinct operations with their
  own target and coordinate semantics.

## Rejected alternatives

### Preserve Aseprite's omitted-axis default

An explicit axis makes an agent-authored request self-describing and schema-valid.

### Restrict flip to ordinary transparent Image Layers

Unlike resize, crop, and canvas-resize, flip changes neither dimensions nor placement;
the native Image operation therefore preserves Background and Reference invariants.

### Apply the active Selection implicitly

That would reintroduce hidden editor state and change whole-Image semantics.

### Flip a Tilemap Image as raw pixels

Packed Tilemap values encode Tile identity and flags and are not ordinary colors.
