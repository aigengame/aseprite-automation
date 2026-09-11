# ADR-0027: Keep Cel existence and raster editing explicit

## Status

Accepted

## Context

In Aseprite, a Cel is the object at a Layer and Frame intersection. `Layer:cel()`
returns `nil` when no Cel exists there. That native absence is different from an
existing Cel whose Image is fully transparent or otherwise contains no visible
content.

Aseprite's Lua `Sprite:newCel()` replaces an existing transparent-Layer Cel by
clearing the old Cel and adding the new one. Interactive drawing can also create a
Cel according to editor state or preferences. Reusing either implicit behavior in a
typed automation Operation would make `add` overwrite data or make Paint change both
object lifecycle and pixels without declaring both effects.

## Decision

- `cel add` creates a Cel only when the addressed Layer/Frame intersection is
  unoccupied and the Layer kind supports that lifecycle. An existing Cel produces
  the stable `CEL_ALREADY_EXISTS` failure and no Target Commit.
- Image and Paint Operations that target a Sprite Cel/Image require the Cel and Image
  to exist. An absent Cel produces `CEL_NOT_FOUND`.
- Paint does not expose an implicit `create_if_missing` behavior. An agent that
  intends creation and raster editing composes `cel add` and the Paint Operation in
  one Operation Plan, using the same Lua Operation Kernel handlers as standalone
  execution.
- Replacing an Image, clearing Cel content, removing a Cel, copying a Cel, and linking
  Cels remain explicitly named Operations with distinct contracts.
- `cel remove` applies only where the Layer/Frame intersection can become absent.
  `cel clear` preserves the Cel and follows the Background Layer rules in ADR-0028.
- A later workflow-oriented composite Operation can create and paint when dogfooding
  proves that capability valuable, but it must state both effects and reuse the same
  Kernel semantics rather than implement another Cel creation path.

## Consequences

- `cel add` never destroys existing authored content as a side effect of its native
  implementation primitive.
- Inspection and failure contracts preserve the difference between absent Cel and
  empty Image content.
- Multi-step authoring remains efficient because an Operation Plan performs both
  steps in one Aseprite process and commits one target.
- Issue #13 owns the Cel-existence delivery matrix.
- Background Layer lifecycle follows ADR-0028 rather than being forced through
  transparent-Layer absence semantics.

## Rejected alternatives

### Let `cel add` replace an existing Cel

This copies a surprising `Sprite:newCel()` implementation behavior into a command
whose public verb promises creation.

### Let Paint always create a missing Cel

This hides object creation inside raster editing and can make behavior depend on
undeclared Image size, position, and Layer-kind choices.

### Add a generic `create_if_missing` switch to raster Operations

The Plan already composes the two explicit Operations without another process or
intermediate commit. A generic switch would duplicate lifecycle semantics across the
Paint surface.
