# ADR-0044: Keep Tilemap cells, placements, and canvas mapping explicit

## Status

Accepted

## Consolidates

This record consolidates ADR-0045. Tileset and Tilemap inspection delivery is owned by
issue #41; Tilemap read, replace, patch, and fill contracts are owned by issue #44.

## Context

Aseprite models a Tilemap through a Tilemap Layer. The Layer references one Tileset,
which can also be shared by other Tilemap Layers. It has a Cel only at Frames where
content exists. A Tilemap Cel's Image uses the tilemap pixel format: each Image pixel
encodes a Tile Index and X/Y/diagonal flags rather than a Color Value.

The Cel Image coordinates and the rendered canvas coordinates are different spaces.
`tile_x/tile_y` select zero-based pixels in the Tilemap Image, measured in Tile Cells.
The Cel's Canvas Pixel position translates the Tileset Grid to form the effective Cel
Grid and Canvas coverage. Treating cell coordinates as canvas pixels would make
inspection and edits depend on hidden conversion.

Native packed placement integers are efficient implementation data but are unsuitable
for an agent contract. ADR-0041 makes Tile Key the persistent authoring reference and
retains current Tile Index as an observation fact. Structured exchange must also keep
complete bounded state distinct from sparse change without creating a second Artifact
data model.

## Decision

- Tilemap Layer, Tilemap Cel, Tilemap Image, Tileset, and Tile remain distinct native
  concepts. SPA projects each native packed Tilemap value as a Tile Placement in the
  Published Language; the projection does not become a native Aseprite concept.
- A Tilemap Layer references exactly one Tileset. Multiple Layers may share it. Cel
  existence at each Frame follows the accepted Cel Existence semantics.
- A Tilemap Cel Image pixel is one Tile Cell. Public `tile_x` and `tile_y` are
  zero-based coordinates local to that Image; region Rectangles use Tile Cell space.
- Inspection returns the Cel's Canvas Pixel position, Tileset Grid, effective Tilemap
  Cel Grid, and computed Canvas coverage. It does not silently replace one coordinate
  space with another.
- A Tile Placement is a discriminated union: `empty`, or `tile` with
  `tile_key`, `flip_x`, `flip_y`, and `flip_diagonal` booleans.
- Mutation accepts only those Tile Placement variants. It does not accept a packed
  native integer, Base Index, or bare Tile Index.
- Inspection additionally reports current Tile Index. If a native packed Tilemap value
  refers to an existing unkeyed Tile, it returns `tile_key: null` with the Index and flags;
  it never drops the cell or invents a Key.
- A Tile Region Snapshot represents one complete bounded Tile Cell Rectangle. Empty
  Tile is the declared default, and its canonical sparse entries contain every
  non-empty Tile Placement in ascending `tile_y`, then `tile_x` order. Duplicate or
  out-of-Rectangle entries are invalid.
- An observation entry can have `tile_key: null`; a mutation Snapshot requires a Tile
  Key for every non-empty Tile Placement.
- A replacement Snapshot writes Empty Tile to every omitted coordinate. A Tilemap Patch
  is a distinct value in which omitted coordinates retain their current Tile Placements.
- Inline JSON and JSON Artifacts use the same Snapshot representation. Crossing the
  inline Operation Limit selects the complete Artifact projection or
  fails with typed bounds; it never silently truncates data.
- Cell mutation requires an existing Tilemap Cel unless a separate Cel lifecycle
  Operation is explicitly composed with it.

## Consequences

- Agents can reason separately about map topology, Tile identity, transform flags,
  bounded exchange, and rendered Canvas position.
- Existing unkeyed native content stays observable while stable authoring inputs use
  Tile Keys.
- Complete state and sparse intent each have one unambiguous representation across
  CLI, Skill, MCP, and Artifact transport.

## Rejected alternatives

- Canvas Pixels do not directly index a Tilemap Cel Image.
- Packed placement integers conflate current Index and transform flags.
- One sparse value cannot mean both complete replacement and partial change.
- Dense and sparse public Snapshot encodings would duplicate normalization rules.
- Dropping unkeyed Tile Placements would make inspection incomplete.
- Artifact transport does not justify a second Tilemap representation.
