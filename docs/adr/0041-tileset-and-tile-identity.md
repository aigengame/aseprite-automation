# ADR-0041: Separate native tile indexes from persistent Tile Keys

## Status

Accepted

## Context

Aseprite exposes `Sprite.tilesets` as a one-based Lua collection. Internally and in
the `.aseprite` format, Tilemap Layers refer to Tilesets by zero-based collection
position. The format calls that position a Tileset ID, but decoding maps it to the
new collection order; the Lua `Tileset` object exposes no ID or UUID. Tileset names
are ordinary strings and are not constrained to be unique. Multiple Tilemap Layers
can share one Tileset.

Within a Tileset, `Tile.index` is native and zero-based. Index 0 is the mandatory
Empty Tile and cannot be deleted. A Tilemap Image encodes the current Tile Index plus
X/Y/diagonal transform flags. Adding, deleting, or reordering Tiles can change later
indexes and requires Aseprite to remap placements. Issues #43 and #55 own the
prototype evidence for this identity boundary.

`Tileset.baseIndex` is persisted, but its function is presentation: Aseprite displays
`tile_index + base_index - 1`. It does not change the index encoded in Tilemap data.
Aseprite exposes no independent persistent Tile ID, but each Tile supports persistent
custom properties. Agent workflows need semantic Tile references that survive native
index changes.

## Decision

- SPA calls the current one-based `Sprite.tilesets` position `tileset_index`.
  Zero-based native and file-format references are private Lua Kernel details.
- A direct Tileset target accepts exactly one of current `tileset_index` or
  `tileset_name`. A name must match exactly once. Layer-scoped Operations can instead
  resolve the Tileset referenced by one exactly addressed Tilemap Layer.
- Tileset Index is a current-snapshot address, not a Persistent Identity. SPA does
  not expose an internal Tileset ID or introduce a Tileset UUID or Tileset Key.
- SPA publishes Aseprite's persisted `Tileset.baseIndex` as `base_index` and reports
  its display role. It is never accepted as an address or Tile Index.
- `tile_index` is Aseprite's native zero-based Tile position. Index 0 is the Empty
  Tile, cannot be removed, and has no Tile Key.
- `tile_key` is a caller-supplied, non-empty string stored in the documented,
  versioned `aigengame.spa` Tile properties namespace. It must be unique among the
  non-empty Tiles of one Tileset; it is not globally unique.
- Every non-empty Tile created through SPA requires a Tile Key. Existing unkeyed or
  duplicate-keyed Tiles remain completely inspectable, and no read Operation writes
  or repairs metadata implicitly.
- A current Tile Index can be used to inspect a Tile or explicitly assign a missing
  Tile Key. Persistent Tile references and Tile Placements use Tile Key within an
  exactly resolved Tileset. Results return both the Key and current Tile Index.
- A missing Key fails as not found and a duplicate Key fails as ambiguous. Validation
  can report missing or duplicate Keys as Findings without making the Sprite unreadable.
- Fixed Tile Operations preserve generic Tile user data and unrelated author or
  plugin properties when writing the SPA namespace.
- Any Operation that changes Tile Indexes must declare and apply placement remapping
  or remain unsupported. Issue #43 owns persistence acceptance.

## Consequences

- Public contracts match Aseprite's native indexing while giving agents durable
  semantic references for authored Tiles.
- Existing Aseprite documents can be inspected before opting into SPA Tile metadata.
- Tile Key is a functional authoring mechanism, not a general identity subsystem.
- A shared Tileset can be found through a persistent Layer UUID when a stable owning
  workflow anchor exists; orphan Tilesets require fresh collection inspection or a
  unique name.

## Rejected alternatives

### Treat Tile Index as persistent identity

Native lifecycle operations can move indexes and remap placements. Current position
therefore cannot satisfy persistent identity.

### Use Base Index as an address

Base Index is a persisted presentation offset, not a stored Tile or Tileset identity.

### Assign keys while reading an existing Sprite

Inspection must not mutate the document or claim user metadata without explicit intent.

### Require existing documents to have complete unique keys before inspection

That would make valid native Aseprite documents unreadable. Missing and duplicate
Keys are observable state and optional Validation Findings.

### Add Tileset UUIDs or a universal identity registry

Current Tileset workflows can use snapshot-relative index, unique name, or a
persisted Tilemap Layer UUID. A second identity system has no accepted functional need.

### Generate opaque Tile UUIDs

Agent workflows benefit from caller-chosen semantic keys such as `ground` or
`ladder`, scoped to one Tileset. Opaque global identifiers add no required capability.
