# ADR-0023: Use Layer-specific exact addressing

## Status

Accepted

## Context

SPA must address nested Layers and Layers with duplicate names without relying on
the editor's active Layer. Aseprite does not define a native Layer path or a unified
Selector. Its Layer collections support one-based indexing and name lookup, but
name lookup returns the first case-insensitive match. `Layer.stackIndex` is local to
the Layer's parent, and `Layer.uuid` is persistent only when the Sprite enables
Layer UUID persistence.

UUID-only addressing would exclude valid existing Sprites whose Layer UUIDs are not
persisted. Name-only addressing cannot distinguish duplicate names. A mixed generic
query language would add concepts beyond the Layer behavior that needs them.

## Decision

Each Layer Operation documents which of these Layer-specific target fields it
accepts and applies its own target-count rule:

- `layer_uuid` addresses one Layer when the UUID is persisted by the Sprite.
- `layer_stack_path` is a non-empty sequence of one-based `Layer.stackIndex`
  values from the Sprite root through parent groups to the target Layer.
- `layer_name` is a convenience form that succeeds only when exactly one Layer in
  the Operation's documented search scope has that name.

The Lua Operation Kernel resolves these document-dependent fields. A missing target,
an invalid stack path, an unpersisted UUID, or a name with zero or multiple matches
produces a typed Failure Envelope. SPA never inherits Aseprite's first-name-match
behavior for a mutation.

Layer inspection returns each Layer's name, hierarchy, current `layer_stack_path`,
and `layer_uuid` when it is persistent. An Operation that moves or reparents a Layer
returns its resulting address facts.

`layer_stack_path` is a current structural address, not a Persistent Identity. SPA
does not add input digests, locks, or concurrency coordination to make it one.

## Consequences

- Nested and duplicate-named Layers remain addressable even in existing Sprites
  that do not persist Layer UUIDs.
- Agents can copy current address facts from inspection into a mutation request.
- Reordering or reparenting can invalidate an earlier stack path, so structural
  mutation results expose the resulting path.
- Operations state the search scope for `layer_name` and their allowed target count
  rather than inheriting a global selection policy. Issue #8 owns the first delivery
  matrix.
- The design remains Layer-specific and does not revive a universal Selector or
  Locator abstraction.

## Rejected alternatives

### Use Layer names and accept Aseprite's first match

This can silently mutate the wrong Layer when names are duplicated.

### Require persisted Layer UUIDs for every existing Sprite

This would either reject otherwise editable files or force an implicit document
mutation merely to address a Layer.

### Introduce a universal object selector

Frames, Cels, Layers, Slices, Tiles, and pixel regions have different native
addressing semantics. A cross-domain query model adds abstraction without a shared
behavioral invariant.
