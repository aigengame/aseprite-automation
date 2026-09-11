# ADR-0042: Preserve Tile Placements during Tile addition and removal

## Status

Accepted

## Context

ADR-0041 makes Tile Key the persistent agent-facing reference while native Tile
Index remains an observable storage position. Tile lifecycle can change those
positions, so its behavior must preserve what existing Tile Placements mean.

Aseprite 1.3.18.5 exposes optional indexed insertion through `Sprite:newTile()` and
deletion through `Sprite:deleteTile()`. Source inspection shows that these Lua paths
insert or erase the Tileset entry but do not perform the complete `RemapTilemaps`
behavior used by native editing workflows. Wrapping them directly can therefore
leave Tilemap Images pointing at shifted indexes with different semantic Tiles.
The second prototype also demonstrated that a requested insertion position was not
a reliable save/reopen identity.

Appending does not shift existing Tile Indexes. Removal always shifts higher
Indexes, and removing a used Tile additionally needs a caller decision about the
affected cells. Because a Tileset can be shared, the affected set spans every
referencing Tilemap Layer, Frame, and Cel.

## Decision

- `tileset tile add` always appends one non-empty Tile and requires its unique Tile
  Key. It does not accept an insertion position.
- `tileset tile remove` targets one non-empty Tile by Tile Key. Empty Tile Index 0
  cannot be removed.
- Before mutation, the Lua Operation Kernel resolves and validates every Tilemap
  Layer, Cel, and Tile Placement that references the Tileset. Invalid or out-of-range
  placement data fails the Operation.
- If no Placement uses the target Tile, the request needs no replacement. If any
  Placement uses it, the request must choose either the Empty Tile or another Tile
  Key in the same Tileset as the Tile Removal Replacement.
- The Kernel computes the complete old-to-new Tile Index mapping before mutation.
  The removed Index maps to the replacement's post-removal Index, every old Index
  above the removed Index decrements by one, and every lower Index remains unchanged.
- The Kernel rewrites all applicable Tile Placements, preserving each X-flip,
  Y-flip, and diagonal-flip flag, and removes the Tile in the same all-or-nothing
  Mutation. No partially remapped Target is committed.
- The Operation rereads the resulting Tileset and Placements. Its result includes
  the complete Index mapping, resulting Key-to-Index facts, replacement, and every
  affected Layer, Cel, and Tile Cell.
- Missing or ambiguous Keys and a used Tile without a replacement fail before
  mutation. SPA never chooses a visually similar Tile, deduplicates Images, or
  silently maps a used Tile to Empty.
- Tile reorder is not implied by add/remove; ADR-0043 defines it as a distinct
  complete-permutation Operation.

## Consequences

- Agents can evolve a Tileset without silently changing the meaning of existing maps.
- Shared-Tileset impact is explicit and verifiable across the whole Sprite.
- Append-only creation removes an unnecessary positional input while Tile Key carries
  the stable authoring intent.
- Removal cost scales with complete Tileset usage, which is required functional work
  rather than a generalized consistency subsystem.
- Tests must cover replacement Indexes both above and below the removed Index, because
  the replacement's final position differs in those cases.

## Rejected alternatives

### Expose arbitrary insertion position

It shifts existing Indexes without adding stable authoring value. Tile Key expresses
identity, while an explicit reorder capability can later own ordering semantics.

### Directly wrap Sprite:newTile and Sprite:deleteTile

The Lua methods do not provide the complete placement-remapping behavior required by
SPA's accepted semantics.

### Refuse removal whenever the Tile is used

That is safe but unnecessarily blocks the common functional intent of replacing or
clearing all uses before deletion.

### Always replace a removed Tile with Empty

Clearing authored cells is a user-visible decision and cannot be inferred.

### Match a replacement by Image similarity

Visual similarity is not Tile identity and introduces an implicit policy that agents
cannot reliably predict or verify.
