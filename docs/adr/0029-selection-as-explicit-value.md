# ADR-0029: Represent Selection as an explicit canonical value

## Status

Accepted

This ADR consolidates the durable cross-feature decisions from ADR-0030. Issue
#24 owns the exact feature contract and acceptance.

## Context

Aseprite exposes the current Document Selection as a binary pixel Mask, but the
current Sprite file lifecycle does not preserve that editor state. SPA must
transport arbitrary Selection shapes across isolated Operations without
claiming a file mutation or preserving hidden Plan state. A preview image does
not carry sufficient origin and Mask semantics to be the authority.

## Decision

- SPA retains Aseprite's term **Selection** and represents it as an explicit,
  serializable binary Mask value in Canvas Pixel space.
- Selection-producing Operations return this value. Image, Paint, and other
  consumers receive it explicitly instead of reading a prior process or Plan
  state.
- An omitted Selection means no restriction. `empty` selects no pixels, and
  `all` carries the exact selected Canvas Rectangle.
- A `mask` carries tight half-open bounds and ordered rows. Each row contains
  an absolute Canvas `y` and sorted positive-length `{x, length}` runs.
  Runs do not overlap, adjacent runs are merged, and the bounds have no
  unselected outer row or column.
- Construction geometry and set-operation history are request forms, not
  variants of the resulting Selection value.
- Inline and `selection-mask` JSON Artifact forms use the same schema. A PNG
  can be a derived Preview Artifact but is not authoritative or assumed
  reversible.
- The Lua Operation Kernel owns normalization, native Selection
  materialization, and result encoding. Python can validate statically
  decidable wire invariants but does not implement Mask behavior.

## Consequences

Selection-dependent edits are reproducible across channels and invocations.
Equivalent binary coverage has one comparable representation, while empty,
all-canvas, and omitted intent remain distinct.

## Rejected alternatives

Persisting editor Selection would claim state absent from the Sprite file.
Plan-only current Selection introduces a second execution model. Construction
history is not a canonical Mask, and PNG introduces unrelated color, alpha, and
threshold rules.
