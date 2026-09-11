# ADR-0047: Remove a Tileset only after its Layer references are resolved

## Status

Accepted

## Context

Aseprite 1.3.18.5 allows `Sprite:deleteTileset()` to delete a Tileset that is still
referenced. Its Lua implementation first changes every referencing Tilemap Layer to
Tileset collection index 0 and contains a TODO to improve that behavior. Retaining
the same packed Tile Indexes while changing the referenced Tileset does not preserve
Tile Key meaning, Tile imagery, Grid behavior, or the rendered result.

SPA must expose Tileset deletion without importing that hidden fallback. It must
also retain the complete user capability: an agent can explicitly rebind Layers and
then remove the old Tileset within the existing single-document Operation Plan.

## Decision

- `tileset remove` exactly addresses one Tileset and resolves every Tilemap Layer
  that references it before mutation.
- When one or more references exist, the Operation fails with `TILESET_IN_USE`,
  returns the complete referencing Layer facts, and performs no mutation.
- SPA never uses Aseprite's implicit reassignment to Tileset 0 as the public removal
  semantic.
- Explicit Layer-to-Tileset rebinding is a separate Core Operation Semantic. An
  agent can compose every required rebind followed by `tileset remove` in one
  Operation Plan, which reuses the standalone handlers and commits atomically.
- Successful removal returns the complete removed Tileset facts, the old-to-new
  Tileset Index mapping, and every surviving Tilemap Layer binding.
- Postconditions and save/close/reopen verification prove the resulting collection,
  indexes, and Layer relationships.
- SPA does not introduce a general orphan scanner, implicit garbage collection, or
  background cleanup policy.

## Consequences

- A destructive lifecycle Operation cannot silently change the meaning of existing
  Tile Placements.
- Rebinding and deletion remain independently inspectable and reusable while Plans
  preserve an atomic multi-step authoring intent.
- Collection reindexing is visible without treating Tileset Index as persistent
  identity.
- The rule addresses a verified Aseprite seam without creating lifecycle
  infrastructure unrelated to sprite authoring.

## Rejected alternatives

### Mirror Aseprite's Tileset 0 fallback

Collection position is not identity, and matching Tile Index numbers do not prove
matching Tile meaning or appearance.

### Add a replacement parameter to `tileset remove`

That would duplicate the placement and Grid semantics of the reusable Layer
rebinding Operation. Plans already provide atomic composition of both operations.

### Delete referencing Tilemap Layers

Removing a Tileset does not imply removing authored Layer content.

### Add automatic orphan collection

SPA can remove the exact transient Tileset it creates in ADR-0046 and explicitly
remove any other unreferenced Tileset. A general collector is not required.
