# ADR-0029: Represent Selection as an explicit value

## Status

Accepted

## Context

Aseprite exposes `Sprite.selection` as a native pixel Mask for the current Document.
The scripting API can read, replace, combine, invert, and transform it. However, the
current `.aseprite` writer does not persist the active Selection, and the deprecated
file-format Mask Chunk is ignored when read. A Selection set in one isolated SPA
invocation therefore cannot be recovered by reopening the Sprite File in the next.

Treating `selection set` as a normal saved mutation would claim a Target Commit that
does not contain the result. Carrying a hidden current Selection in an Operation Plan
would add stateful, Plan-only semantics and make ordinary Operations behave
differently depending on prior steps.

## Decision

- SPA retains Aseprite's term **Selection** and represents it in the Published
  Language as an explicit serializable pixel Mask value in Canvas Pixel space.
- Selection Operations such as create, combine, invert, grow, shrink, transform, and
  validate accept and return Selection values. They do not claim to persist
  `Sprite.selection` in a Target Sprite File.
- Image, Paint, copy, move, erase, and other Selection-consuming Operations receive
  the Selection explicitly in their request.
- The Lua Operation Kernel may materialize a Selection value as a native Selection
  while executing an Operation so it can reuse Aseprite's behavior. That transient
  object is not part of Target Commit.
- Omission of a Selection request field means no Selection restriction. An explicit
  empty Selection selects zero Canvas Pixels. An explicit all-canvas Selection
  selects every Canvas Pixel. These meanings are distinct.
- A caller can pass the same Selection value or Artifact explicitly to multiple Plan
  Steps. SPA does not introduce a hidden current Plan Selection, a named selection
  session, or Plan-only Selection mutation commands.
- A larger Selection can use an explicitly supported Artifact projection with the
  same bounds and Mask semantics.
- Inline and Artifact forms use the canonical binary Selection Encoding in ADR-0030.
  A PNG can be produced as a Preview Artifact but is not the Selection authority.

## Consequences

- Selection-dependent edits are reproducible across isolated CLI and MCP calls.
- Operation Results do not claim that a transient editor Mask was saved.
- Agents can construct and reuse complex Selections without a persistent editor
  process.
- Selection remains native domain language while its transport is adapted for
  agent automation.
- Canonical encoding and Artifact parity follow ADR-0030.

## Rejected alternatives

### Persist `Sprite.selection` through the Sprite File

The supported Aseprite file lifecycle does not preserve that state.

### Restrict Selection commands to Operation Plans

This introduces a hidden current-selection state and a second execution model for
otherwise channel-neutral Operations.

### Interpret an empty Selection as the whole canvas

That makes an explicit value indistinguishable from omission and can turn an intended
no-op into a full-image mutation.
