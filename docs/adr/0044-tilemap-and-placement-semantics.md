# ADR-0044: Keep Tilemap cells, placements, and canvas mapping explicit

## Status

Accepted

## Context

Aseprite models a Tilemap as a native Layer kind. The Layer references one Tileset,
which can also be shared by other Tilemap Layers. Like an Image Layer, it has a Cel
only at Frames where content exists. A Tilemap Cel's Image uses the tilemap pixel
format: each Image pixel encodes a Tile Index and X/Y/diagonal flags rather than a
Color Value.

The Cel Image coordinates and the rendered canvas coordinates are different spaces.
`tile_x/tile_y` select zero-based pixels in the Tilemap Image, measured in Tile Cells.
The Cel's Canvas Pixel position translates the Tileset Grid to form the effective Cel
Grid and Canvas coverage. Treating cell coordinates as canvas pixels would make
inspection and edits depend on hidden conversion.

Native packed placement integers are efficient implementation data but are unsuitable
for an agent contract. ADR-0041 makes Tile Key the persistent authoring reference and
retains current Tile Index as an observation fact. Existing valid Aseprite documents
can contain Tiles without SPA keys and must remain completely inspectable.

## Decision

- Tilemap Layer, Tilemap Cel, Tilemap Image, Tileset, Tile, and Tile Placement remain
  distinct native concepts in the Published Language.
- A Tilemap Layer references exactly one Tileset. Multiple Layers may share it. Cel
  existence at each Frame follows the accepted Cel Existence semantics.
- A Tilemap Cel Image pixel is one Tile Cell. Public `tile_x` and `tile_y` are
  zero-based coordinates local to that Image; region Rectangles use Tile Cell space.
- Inspection returns the Cel's Canvas Pixel position, Tileset Grid, effective Tilemap
  Cel Grid, and computed Canvas coverage. It does not silently replace one coordinate
  space with another.
- The public Tile Placement Value is a discriminated union: `empty`, or `tile` with
  `tile_key`, `flip_x`, `flip_y`, and `flip_diagonal` booleans.
- Mutation accepts only those Placement Value variants. It does not accept a packed
  native integer, Base Index, or bare Tile Index.
- Inspection additionally reports current Tile Index. If a native Placement refers
  to an existing unkeyed Tile, it returns `tile_key: null` with the Index and flags;
  it never drops the cell or invents a Key.
- `tilemap get`, `tilemap set`, and `tilemap fill` target exactly one Tilemap Layer
  through Layer Addressing and one one-based Frame Number. They require an existing
  Tilemap Cel at that intersection.
- Missing Cels fail without implicit creation. `cel add` and a Tilemap write can be
  composed in one Operation Plan using the same standalone Core Operation Semantics.
- A write Rectangle outside the Tilemap Image fails unless the specific Operation
  declares caller-selected clipping. A clipped success reports the applied Tile Cell
  Rectangle.

## Consequences

- Agents can reason separately about map topology, Tile identity, transform flags,
  and rendered canvas position.
- Existing unkeyed native content stays observable while stable authoring inputs use
  Tile Keys.
- Tilemap editing reuses Cel lifecycle and coordinate-space contracts instead of
  introducing hidden editor-state behavior.
- Results carry enough geometry to relate a bounded cell observation to its canvas
  effect without a general spatial framework.

## Rejected alternatives

### Address cells in Canvas Pixel space

Canvas positions depend on Cel position and Grid conversion and do not directly index
the Tilemap Image.

### Expose packed tile integers

They conflate mutable Tile Index with transform flags and bypass the stable Tile Key
contract.

### Accept Tile Index for mutation

Indexes can change under Tile lifecycle. They remain useful observation facts but not
persistent authoring references.

### Create a missing Cel during tilemap write

That merges two lifecycle operations and conflicts with the accepted explicit Cel
Existence rule. Agents can compose both steps in a Plan.

### Drop placements whose Tiles lack Tile Keys

That would make inspection incomplete and lose valid native Aseprite content.
