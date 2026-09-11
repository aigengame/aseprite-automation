# ADR-0037: Keep Remap Colors Sprite-wide and bound Palette Reorder explicitly

## Status

Accepted

## Context

Aseprite's Remap Colors implementation traverses the Sprite's Images rather than a
Frame Range, and `Sprite.transparentColor` is one Sprite-wide Palette Index. It is
therefore incorrect to present native Remap Colors as mutation of one Palette Change.

Palette Reorder is an agent-facing operation with a stronger promise: rendered RGBA
colors remain stable after Entries move. A Palette Change can cover one Frame Range,
but a linked Image can be referenced by Cels both inside and outside that range. If
the Image is remapped in place, the operation also changes the outside Cels. Moving
the global Transparent Color Index for one Palette Change similarly changes how all
other Palette Changes interpret transparency.

Automatically unlinking such Cels would silently change document structure. Silently
expanding the request would violate the declared Palette Change scope. The contract
needs domain-specific scope rules rather than a generic consistency mechanism.

## Decision

- `palette remap` follows Aseprite's Sprite-wide Remap Colors semantics. It accepts
  an explicit old-to-new Palette Index mapping and no Frame Range or
  `palette_frame_number` target.
- Remap Colors rewrites every Indexed Image in the Sprite and remaps the global
  Transparent Color Index when its source index is mapped.
- For each mapped pixel occurrence, the destination index must exist in that Frame's
  Effective Palette. The resulting Transparent Color Index must exist in every
  Palette Change. Any invalid destination fails before mutation.
- `palette reorder` uses a discriminated `scope`:
  - `palette-change` requires one exact `palette_frame_number`. It reorders that
    Palette Change and remaps Images referenced within its effective Frame Range.
    The permutation must leave the global Transparent Color Index fixed. If any such
    Image is also referenced by a Cel outside the range, the operation fails and
    identifies every conflicting reference; the caller can explicitly unlink Cels.
  - `sprite` applies one Entry permutation to every Palette Change and remaps every
    Indexed Image plus the global Transparent Color Index. The permutation must be
    valid for every Palette Change.
- A reorder permutation is bijective over the Entries it moves; indexes not moved by
  the declared permutation remain fixed.
- Neither scope unlinks a Cel automatically or broadens itself after target
  resolution.
- Results report the scope, permutation, Palette Changes, Images, Cels, Frames, and
  old/new Transparent Color Index. Typed failures expose invalid destinations and
  cross-range shared-Image references.

## Consequences

- Remap Colors retains the same object scope as Aseprite instead of becoming a
  Frame-scoped imitation.
- Palette Change Reorder can make and verify its rendered-color preservation claim.
- Sprite Reorder supports global Palette organization when every change participates.
- Linked-Cel topology remains explicit and caller-controlled.
- The additional checks are part of Palette editing semantics, not a general
  referential-integrity, locking, or rollback subsystem.

## Rejected alternatives

### Scope Remap Colors to a Frame Range

That departs from the native operation and becomes ambiguous for linked Images that
cross the range.

### Remap every linked Image and report the expanded range

For Palette Change Reorder, expanding into Frames with a different Effective Palette
can change rendered colors and break the operation's primary promise.

### Automatically unlink cross-range Cels

This preserves the requested range by silently changing Cel sharing, which is an
independent authored property.

### Move the Transparent Color Index for one Palette Change

The index belongs to the Sprite and would change transparency under every other
Palette Change.

### Add a generic consistency or reference-integrity service

The required validation is local to Palette Index, Palette Change, Image sharing,
and Transparent Color semantics and belongs in the Palette domain handler.
