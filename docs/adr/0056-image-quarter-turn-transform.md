# ADR-0056: Implement exact Image quarter-turns in the Lua Kernel

## Status

Accepted

## Context

Aseprite 1.3.18.5 exposes native `Image:flip` but no Lua `Image:rotate`. Its editor
`Rotate` command targets a Sprite canvas or Mask and therefore depends on broader
document or editor state. SPA still needs a deterministic, agent-addressable rotation
of one linked Image buffer.

Quarter turns can preserve stored pixels through exact integer coordinate mappings.
Arbitrary angles would introduce interpolation, output-bound, and pivot policies that
are not required by the accepted operation.

## Decision

- Image Quarter-turn Transform is a pure Raster Authoring transform owned and
  implemented once by the fixed Lua Kernel.
- The request requires one integer angle aligned with Aseprite's editor vocabulary:
  - `90` rotates clockwise.
  - `-90` rotates counterclockwise.
  - `180` rotates by a half turn.
- No omitted default, arbitrary angle, modulo normalization, or interpolation is
  accepted.
- For source dimensions `W` by `H`, the transform maps source Image Pixel `(x,y)`:
  - `90`: `(H-1-y,x)`, producing dimensions `H` by `W`.
  - `-90`: `(y,W-1-x)`, producing dimensions `H` by `W`.
  - `180`: `(W-1-x,H-1-y)`, retaining dimensions `W` by `H`.
- The transform preserves Pixel Format, stored pixel values, and mask/transparent
  semantics. It neither reads nor applies Selection state.
- `spa image rotate` composes the transform with one required Cel Position Policy for
  an existing Cel on an ordinary transparent Image Layer:
  - `keep` leaves every affected Cel position unchanged.
  - `pivot` accepts an integer Point in old Image Pixel space. The Point may be
    outside Image bounds because it is a transform anchor. The Kernel extends the
    same discrete mapping to it and applies `old_pivot - rotated_pivot` as the exact
    integer position delta.
- A linked Image is transformed once. The same delta applies to every sharing Cel and
  native links remain intact. Isolated behavior requires `cel unlink` first.
- Background, Reference, Tilemap, absent, and non-Cel targets are rejected. Their
  full-canvas, floating-bound, or Placement semantics belong to separate operations.
- Buffer replacement and all Cel position changes execute as one all-or-nothing
  Mutation.
- Results return angle and mapping, old/new dimensions, position policy, optional
  pivot, applied delta, every affected Cel/link and old/new position, Pixel Format,
  and before/after content digest. Save/close/reopen verifies persisted facts.
- Python must not generate a temporary script or own another rotation algorithm.

## Consequences

- Agents can rotate one Image without manipulating active editor state.
- Quarter turns are lossless for stored values, including Palette Indexes.
- Pivot preservation is exact and needs no rounding policy.
- Sprite, Reference, Selection, and Tilemap rotation remain separate domain behavior.

## Rejected alternatives

### Call `app.command.Rotate` for one Image

The command targets Sprite canvas or Mask state, not one explicitly addressed Image.

### Claim a native `Image:rotate`

That method does not exist in the supported Aseprite Lua API.

### Support arbitrary angles immediately

They require interpolation, output-bounds, and fractional-anchor decisions beyond
this exact stored-pixel transform.

### Implement rotation in Python

That would violate the Lua Kernel's authority over Core Operation Semantics.
