# ADR-0045: Use one canonical sparse Tile Region Snapshot

## Status

Accepted

## Context

ADR-0044 establishes Tile Cell space and typed Tile Placement Values. Prototype
evidence showed that unbounded Cell expansion makes structured observations
unusable, while agents still need a complete reversible form for selected regions,
writes, verification, and portable JSON Artifacts. Issues #41 and #55 own the
measurements and acceptance evidence.

A dense grid makes Empty Cells expensive. A bare sparse patch is smaller but cannot
distinguish "omitted means Empty" from "omitted means unchanged." These are different
authoring intents and must not share ambiguous semantics.

## Decision

- A Tile Region Snapshot contains one Cel-local Tile Cell Rectangle and a `cells`
  list. Empty Tile is the fixed default for every coordinate in the Rectangle.
- `cells` contains every non-empty Placement at absolute Cel-local `tile_x/tile_y`.
  Entries are canonicalized in ascending `tile_y`, then `tile_x` order. Duplicate or
  out-of-Rectangle coordinates are invalid.
- An observation entry includes current Tile Index and can have `tile_key: null` for
  an existing unkeyed Tile. A mutation Snapshot has the same structure but requires
  a Tile Key for every non-empty Placement.
- `tilemap get` without a region returns complete Cel dimensions, Grid/Canvas mapping,
  Tile usage, and other topology summaries without Cell expansion.
- `tilemap get` with an explicit region returns a complete inline Tile Region Snapshot.
- `tilemap set` consumes a mutation Snapshot and replaces the entire Rectangle. Every
  coordinate omitted from `cells` is written as Empty Tile.
- `tilemap patch` is a separate Operation whose unique explicit Cell entries are the
  only coordinates changed. Omitted coordinates retain their current Placements.
- `tilemap fill` writes one Placement Value throughout its Rectangle. SPA does not
  introduce a pattern language at this boundary.
- Complete Cel data that exceeds the inline Domain Bound is available through an
  explicitly selected JSON Artifact using the same Tile Region Snapshot structure.
- Results report exact requested and covered Rectangles and whether the requested
  scope is complete. Exceeding the bound fails with typed allowed-range details or
  uses the selected Artifact projection; it never silently truncates.

## Consequences

- One sparse, reversible representation serves bounded reads, complete replacements,
  verification, and file transport.
- `set` and `patch` make clearing versus preservation explicit for agents.
- Default inspection stays usable on large Tilemaps without weakening completeness
  for its declared topology scope.
- Artifact transport does not create a second Tilemap data model.

## Rejected alternatives

### Return every Cell by default

Unbounded dense output makes structured inspection unusable as maps grow.

### Use one sparse operation for both replacement and patching

Omitted Cells would have two incompatible meanings: Empty or unchanged.

### Add dense and sparse public encodings

One canonical sparse Snapshot is sufficient and avoids format negotiation and
duplicate normalization rules.

### Add a Tile pattern language to fill

It is not required for the foundational Cell workflow. Agents can use Snapshot or
Patch values, and a future evidence-backed authoring Operation can add a named pattern.

### Invent a different full-data Artifact schema

That would create a second representation for the same Tile Region semantics.
