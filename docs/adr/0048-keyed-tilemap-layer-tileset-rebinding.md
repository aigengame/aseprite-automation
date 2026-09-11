# ADR-0048: Rebind a Tilemap Layer through Tile Keys and explicit Grid policy

## Status

Accepted

## Context

Aseprite exposes a writable `Layer.tileset` property for a Tilemap Layer. Assigning a
different Tileset preserves the packed Tile Index values in each Tilemap Cel, but an
equal Index in another Tileset does not establish equal Tile identity or imagery. A
different target Grid also changes how unchanged Tile Cell coordinates cover Canvas
Pixels.

ADR-0047 requires referenced Layers to be explicitly rebound before their old
Tileset can be removed. The reusable rebind behavior must therefore preserve or
deliberately replace Tile meaning, expose spatial consequences, and work both as a
standalone Operation and as a Plan step.

## Decision

- `spa layer set-tileset` exactly addresses one Tilemap Layer and one target Tileset.
  It is a named Operation rather than part of generic `layer set`.
- The request requires one Tile Rebinding Map:
  - `by_key` maps each used non-empty source Tile Key to an identical, unique Key in
    the target Tileset.
  - `explicit` completely maps each used non-empty source Tile Key to one uniquely
    resolved target Tile Key or Empty Tile. Multiple source Keys can deliberately
    map to the same target Key.
- Empty Tile always maps to Empty Tile. Neither mode accepts or infers Tile Index
  mapping, image similarity, or nearest-image replacement.
- Every used source Tile must have a unique Key. Missing mappings, unkeyed or
  duplicate-keyed used source Tiles, and missing or ambiguous target Keys fail
  before mutation.
- The request also requires one Tileset Grid Policy:
  - `require_equal` fails unless source and target Grids are identical.
  - `use_target` keeps every Tile Cell coordinate and Cel Canvas Pixel position,
    performs no resampling, and explicitly accepts the target Grid's effective Grid
    and Canvas coverage.
- The fixed Lua Kernel rewrites Placements in every Cel of the Layer while
  preserving X/Y/diagonal flags, then switches the Layer's Tileset reference in the
  same all-or-nothing Mutation.
- The result returns the complete source-Key to target-Key/Empty and old/new Index
  translation, all affected Cels and Cells, old/new effective Grids and Canvas
  coverage, and the final Layer-to-Tileset relationship.
- Postconditions and save/close/reopen verification confirm every Placement,
  relationship, and reported spatial fact.
- The Operation can precede `tileset remove` inside one Operation Plan. Both
  standalone and Plan entrypoints invoke the same descriptor-owned Lua handler.
- Public navigation remains under Layer lifecycle; the tile-authoring Domain Module
  owns the cross-Layer/Tileset implementation.

## Consequences

- A Tileset change cannot silently reinterpret Tile Indexes as unrelated Tiles.
- Agents can choose semantic matching by Key or explicit replacement, including
  clearing selected Tile meanings to Empty.
- Grid changes remain available but their Canvas consequences are deliberate and
  machine-verifiable.
- Rebinding supplies the reusable semantic required by safe Tileset deletion without
  duplicating it inside `tileset remove`.

## Rejected alternatives

### Expose raw `Layer.tileset` assignment

It preserves numeric indexes while potentially changing every Tile's meaning and
the Layer's rendered appearance.

### Put rebinding inside generic `layer set`

This behavior rewrites every Tilemap Cel and has mapping, Grid, and reporting
contracts far beyond an ordinary Layer property update.

### Always map identical Tile Keys implicitly

Agents also need deliberate replacement or clearing. A discriminated mapping makes
the selected behavior explicit.

### Map Tiles by current Index

Tile Index is a mutable collection position and is not persistent Tile identity.

### Automatically resample when Grids differ

Resampling combines a Tileset relationship change with a separate spatial editing
policy. `use_target` instead preserves Cells and reports the resulting coverage.
