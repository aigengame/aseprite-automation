# ADR-0043: Reorder Tiles through a complete keyed permutation

## Status

Accepted

## Context

ADR-0041 separates persistent Tile Key from mutable native Tile Index, and ADR-0042
requires lifecycle changes to preserve every Tile Placement. Agents also need to
control Tileset order for deterministic authoring and export. Positional operations
such as "move before" depend on a changing snapshot and make a multi-step reorder
hard to validate. Sorting by name, image similarity, or usage would introduce policy
that Aseprite does not define.

A Tile includes more than its Image: Aseprite also persists color, data, and typed
custom Properties. Reordering content without moving all of these values together
would split Tile identity. Because public Lua exposes individual Tile fields rather
than a native reorder operation, real-runtime proof of lossless typed-Property copying
is required before SPA can claim this capability as shipped.

## Decision

- `tileset tile reorder` accepts `tile_key_order`, a complete permutation containing
  every non-empty Tile Key in the exactly resolved Tileset exactly once.
- Empty Tile remains at Tile Index 0. `base_index` remains unchanged.
- Missing, extra, or repeated request Keys fail. An existing unkeyed or duplicate-
  keyed non-empty Tile also fails because the permutation cannot identify it exactly.
- Each Tile's Image, color, data, Tile Key, and unrelated author or plugin Properties
  move together as one semantic object.
- Before mutation, the Lua Operation Kernel resolves all Tiles and every Placement in
  all Tilemap Layers and Cels sharing the Tileset and computes one complete old-to-new
  Tile Index mapping.
- The Kernel reorders Tile contents and rewrites every Placement with that mapping in
  one all-or-nothing Mutation. X-flip, Y-flip, and diagonal-flip flags remain unchanged.
- The result contains the requested and resulting Key order, complete Index mapping,
  affected Layers, Cels, and Tile Cells, and reread Key-to-Index relationships.
- SPA does not infer order from names, Images, usage, Base Index, or current indexes,
  and does not expose partial before/after moves as alternate Core Operation Semantics.
- The Operation remains a non-binding Command Catalog candidate until a real Aseprite
  vertical slice proves lossless movement of every supported typed Property and
  save/close/reopen preservation.

## Consequences

- One declarative request expresses final ordering without intermediate unstable
  states.
- Tile Key remains the identity authority while Tile Index remains the native storage
  and observation fact.
- Existing incomplete or ambiguous Key metadata stays readable but must be repaired
  explicitly before reorder.
- Implementation complexity is accepted only with direct functional evidence; the
  catalog does not overstate unverified support.

## Rejected alternatives

### Expose move-before or move-after operations

They compose through changing indexes and require order-sensitive intermediate state
without improving the final-state contract.

### Accept a partial Key list

The placement of omitted Tiles becomes an implicit policy and makes the resulting
order harder for an agent to predict.

### Sort by Tile Key or another property

Lexical, visual, or usage ordering is not native Aseprite meaning and should be
declared by the caller as the complete permutation.

### Move only Images between indexes

Color, data, Tile Key, and unrelated typed Properties are part of the Tile and must
remain attached to it.

### Claim the command before real-runtime typed-Property proof

The Lua surface suggests an implementation route but does not prove that every
supported persisted value round-trips without loss.
