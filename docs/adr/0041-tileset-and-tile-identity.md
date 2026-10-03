# ADR-0041: Separate native tile indexes from persistent Tile Keys

## Status

Accepted

## Consolidates

The Tile add, remove, and reorder feature contracts formerly recorded in ADR-0042 and
ADR-0043 are owned by issue #43; this record retains their shared identity decisions.

## Context

Aseprite exposes `Sprite.tilesets` as a one-based Lua collection. Internally and in
the `.aseprite` format, Tilemap Layers refer to Tilesets by zero-based collection
position. The Lua `Tileset` object exposes no persistent ID or UUID, names need not
be unique, and multiple Tilemap Layers can share one Tileset.

Within a Tileset, `Tile.index` is native and zero-based. Index 0 is the mandatory
Empty Tile and cannot be deleted. A Tilemap Image encodes the current Tile Index plus
X/Y/diagonal transform flags. Adding, deleting, or reordering Tiles can change later
indexes and requires placement remapping.

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
- Tileset Index is a current-snapshot address, not a persistent identity. SPA does
  not expose an internal Tileset ID or introduce a Tileset UUID or Tileset Key.
- SPA publishes Aseprite's persisted `Tileset.baseIndex` as `base_index` and reports
  its display role. It is never accepted as an address or Tile Index.
- `tile_index` is Aseprite's native zero-based Tile position. Index 0 is the Empty
  Tile, cannot be removed, and has no Tile Key. Empty Cell detection uses the full
  packed value, as defined by ADR-0044; an index of zero alone is insufficient.
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
  reports missing, invalid, or duplicate Keys as Findings without making the Sprite
  unreadable. Identity fields use the same property projection; an unrepresentable
  Key remains observable through its property result and has a null identity field.
- Fixed Tile Operations preserve generic Tile user data and unrelated author or
  plugin properties when writing the SPA namespace.
- Property observation and native user-data preservation have separate responsibilities.
  Tile Authoring owns one conversion from the public Lua Properties API to typed
  observations within an explicit namespace scope. It reports what Lua retains,
  without inferring file storage types or reconstructing information already lost
  by the native API. Issue #41 defines the current reading subset for inspection
  and authoring assistance. Later accepted needs can extend that subset within
  native Aseprite capabilities; the boundary is not a permanent feature prohibition.
- Any Operation that changes Tile Indexes must preserve or explicitly replace every
  affected Tile Placement. It cannot reinterpret unchanged numeric indexes as identity.

## Consequences

- Public contracts match Aseprite's native indexing while giving agents durable
  semantic references for authored Tiles.
- Existing Aseprite documents can be inspected before opting into SPA Tile metadata.
- Tile Key is a functional authoring mechanism, not a general identity subsystem.
- A shared Tileset can be found through a persistent Layer UUID when a stable owning
  workflow anchor exists; orphan Tilesets require fresh collection inspection or a
  unique name.

## Rejected alternatives

- Tile Index cannot be persistent identity because lifecycle operations can move it.
- Base Index is a presentation offset, not identity.
- Assigning Keys during inspection would make a read mutate valid native content.
- Requiring complete Keys before inspection would make valid Aseprite documents
  unreadable.
- Opaque global Tile UUIDs and a Tileset identity registry add no accepted authoring
  capability.
