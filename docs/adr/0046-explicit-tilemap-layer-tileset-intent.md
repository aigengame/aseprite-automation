# ADR-0046: Require explicit Tileset intent when adding a Tilemap Layer

## Status

Accepted

## Context

A Tilemap Layer is a native Layer that must reference one Tileset. The second
prototype confirmed an important Aseprite lifecycle seam: native Tilemap Layer
creation implicitly creates a Tileset. Reassigning that new Layer to a shared
Tileset does not remove the implicit one, leaving an orphan unless SPA performs the
cleanup.

Agents must be able to create both independent and shared-Tileset Layers without
depending on active editor state or silently changing the Sprite's existing Layer
or Tileset structure. The public operation also needs to preserve the native fact
that the object being added is a Layer, while assigning the cross-object behavior
to the cohesive tile-authoring implementation.

## Decision

- `layer add` declares a native Layer `kind`, including `tilemap`.
- `kind: tilemap` requires exactly one Tilemap Layer Tileset Intent:
  `tileset.create` or `tileset.share`.
- `tileset.create` supplies a new Tileset name, Grid, and Base Index. The Operation
  creates and binds it, then returns the complete resulting Layer and Tileset facts.
- `tileset.share` uses normal exact Tileset Addressing. The target must resolve to
  exactly one existing Tileset before mutation begins.
- When native Tilemap Layer creation produces an implicit Tileset during `share`,
  the fixed Lua Kernel binds the new Layer to the selected Tileset and deletes only
  that newly created orphan inside the same all-or-nothing Mutation.
- Neither an active Tileset, an editor preference, nor Tileset 0 is an implicit
  default.
- The Sprite's existing initial Raster Layer is preserved. Removing it is the
  separate `layer remove` Operation.
- The result and save/close/reopen verification include the Layer UUID where
  persisted, the exact Layer-to-Tileset relationship, and the total Tileset count.
- The public Operation remains `layer add` because it owns Layer membership. Its
  `tilemap` variant is implemented by the tile-authoring Domain Module, which owns
  the cohesive Layer/Tileset native lifecycle seam.

## Consequences

- Agents express whether Tileset sharing is intended instead of inheriting hidden
  editor state.
- SPA removes a known native orphan side effect without adding a general orphan
  collector or cleanup subsystem.
- Layer navigation remains Aseprite-aligned while implementation ownership can
  cross the Layer/Tileset seam where the behavior is cohesive.
- Adding a Tilemap Layer does not silently turn an existing Sprite into a
  tilemap-only document.

## Rejected alternatives

### Put Tilemap Layer creation under `tilemap`

The object being added is still a native Layer. Splitting Layer membership across
two public lifecycle groups would obscure that fact and duplicate hierarchy rules.

### Choose the active or first Tileset by default

That depends on editor state or collection position and makes the same request
produce different structure.

### Keep the implicit Tileset after sharing

This leaves an unintended orphan and makes Tileset counts and later addressing
depend on an implementation side effect.

### Automatically delete the initial Raster Layer

Adding one Layer does not imply removal of another. Tilemap-only structure is an
explicit composition of Layer lifecycle Operations.

### Add a general orphan-cleanup mechanism

The verified problem is local to this native creation seam. The fixed handler can
remove the exact orphan it just created without introducing broader lifecycle
governance.
