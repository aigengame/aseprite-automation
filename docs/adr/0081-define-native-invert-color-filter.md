# ADR-0081: Define native Invert Color Filter

## Status

Accepted

## Context

Aseprite exposes Invert Color as a native pixel Filter with only channel selection.
RGB, Grayscale, and Indexed component paths complement each selected 8-bit component.
Indexed component results are mapped back through the active Palette's RGB Map.

The Indexed Index path instead complements the stored byte directly with XOR `0xff`,
equivalent to `255 - index`. Unlike Color Curve's Index path, Invert Color does not
clamp that output to the active Palette size. An Indexed Sprite whose Effective
Palette has fewer than 256 Entries can therefore receive an index that has no valid
Palette Entry.

SPA's accepted Indexed model requires Palette Index Color Values to be valid in the
applicable Effective Palette, and Palette shrink refuses to orphan used indexes.
Allowing Invert Color to violate the same invariant would make subsequent inspection,
validation, conversion, and export ambiguous. The relevant output can be computed
from actual participating source indexes before mutation without implementing the
Filter's color-processing algorithm.

Inversion is exactly self-inverse for stored RGB/Grayscale components and for a valid
Index byte. Indexed component processing can lose information through Palette lookup
and RGB Map quantization, so the operation cannot promise general two-pass reversal.

## Decision

- `spa filter invert-color` is a deterministic pixel Filter Operation that delegates
  to Aseprite's native Invert Color command through one fixed Lua Kernel handler.
- It has no color, amount, strength, blend, or tonal parameter. The request requires
  explicit Filter Channels.
- RGB accepts a non-empty `components` subset of `red`, `green`, `blue`, and `alpha`.
  Grayscale accepts a non-empty subset of `gray` and `alpha`.
- Indexed requires one-based `palette_frame_number` and exactly one interpretation:
  - `components` accepts a non-empty RGBA subset, resolves source colors through that
    Effective Palette, applies native component inversion, and quantizes through its
    RGB Map.
  - `index` applies the native stored-byte transformation `255 - index`.
- Before Indexed `index` mutation, the fixed Lua Kernel reads every participating
  stored index after Filter Cels Target and Selection resolution. Every source index
  and every calculated native inverted index must identify an Entry in the declared
  Effective Palette. Any invalid result fails the whole Operation before invocation.
- The typed invalid-index Failure reports each relevant source Index, its native
  inverted Index, the Palette size and change facts, and affected target locations.
- SPA does not expand the Palette, clamp an Index, change Channels, switch to component
  processing, or rewrite pixel data to make an invalid Index result acceptable.
- Invert Color always requires Filter Cels Target and accepts explicit pixel Selection
  Application. It has no Filter Application field and never mutates Palette Entries.
- Background Alpha, target eligibility, Linked Image, all-or-nothing mutation, state
  restoration, and persistence rules apply. An Alpha request fails if any target is a
  Background Cel.
- The request accepts no Tiled Mode, amount, interpolation, blend ratio, alternate
  color space, custom center, or caller-defined inversion function.
- Aseprite owns component and Index inversion, component projection, Palette lookup,
  and RGB Map quantization. The preflight computes only the exact native Index
  postcondition required to validate the target domain; Lua and Python do not
  implement an alternate mutation.
- The Operation does not promise that applying it twice restores the original. Exact
  involution is a reported observation for RGB, Grayscale, and valid Index paths;
  Indexed component processing reports its actual quantized result.
- The Operation Result reports effective Channels, explicit Palette basis where
  applicable, Filter Cels Target and Selection facts, unique Images and all affected
  Cels, changed pixel/index counts and bounds, involution-relevant actual observations,
  and persisted before/after content.
- Delivery requires real-runtime parity for every component, mixed Channels, Indexed
  component and valid Index paths, Palette-size boundary cases, Selection, Background
  and linked targets, rollback, restoration, two-pass witnesses, and save/reopen
  verification.

## Consequences

- Agents can use native component and Index inversion without creating Indexed data
  that contradicts SPA's Palette model.
- The guard is a target-data validity rule, not a new security, consistency, or
  transaction subsystem.
- Quantization loss remains observable rather than hidden behind a false reversibility
  guarantee.
- Aseprite remains the sole inversion implementation.

## Rejected alternatives

### Permit out-of-Palette Index results

That would contradict the accepted Palette Index contract and make the resulting
Sprite's colors undefined within SPA's Published Language.

### Clamp the inverted Index

Aseprite's Invert Color Index path does not clamp. Doing so would create a different
operation.

### Automatically expand the Palette

That would add an undeclared Palette lifecycle mutation and change rendered meaning
beyond the requested Filter.

### Fall back to component inversion

Index and component modes are distinct native operations. A failed precondition cannot
silently change the requested interpretation.

### Promise universal two-pass restoration

Indexed component processing can quantize to a different Palette Entry and lose the
original value.
