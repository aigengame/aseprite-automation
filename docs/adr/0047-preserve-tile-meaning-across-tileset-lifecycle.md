# ADR-0047: Preserve Tile meaning across Tileset lifecycle changes

## Status

Accepted

## Consolidates

This record consolidates ADR-0048, ADR-0049, and ADR-0050. Issue #45 owns
rebind/remove and their Plan composition. Issue #175 owns the deferred resize
feature contract after the owner-approved split on 2026-10-04.

## Context

Aseprite can delete a referenced Tileset by changing its Tilemap Layers to collection
index 0 while retaining packed Tile Indexes. Assigning `Layer.tileset` similarly keeps
numeric Placements even when the target Tileset gives those numbers different meaning
or uses a different Grid. `Tileset.grid` has no public Lua setter. A scoped replacement that preserves
authored metadata remains an unverified native prerequisite; whole-Sprite resizing
is not evidence of that capability.

These lifecycle seams affect every referencing Layer, Cel, Tile Placement, Tile Bitmap,
and effective Canvas coverage. SPA must preserve or explicitly replace authored meaning
without inventing hidden cleanup or index-matching policy.

## Decision

- A referenced Tileset cannot be removed until every Layer reference is explicitly
  resolved. SPA never exposes Aseprite's implicit reassignment to Tileset 0 as public
  removal behavior.
- Tileset rebinding maps used Tiles by Tile Key to a target Tile Key or Empty Tile. It
  never infers identity from current Index or Image similarity.
- Rebinding declares how equal or different source and target Grids are handled. A Grid
  change cannot be hidden behind an ordinary Layer property assignment.
- Planned Tileset Grid change uses replacement-style lifecycle composition, not a
  writable `tileset set` field. It must construct the replacement, retain authored
  Tile/Tileset data, rebind Layers, and remove the old Tileset as one Mutation.
  Do not register callable resize until the required public native preservation
  path is verified. The current deferral can change with accepted requirements
  and focused native evidence; it is not a permanent domain restriction.
- Replacement does not claim that persistent Tileset identity survived. Resulting
  collection positions remain current-snapshot facts.
- Tile Bitmap transformation and Tilemap Cel-position behavior are independent explicit
  policies. Tile Cell dimensions, Placement meaning, and native transform flags are not
  implicitly resampled with Tile Bitmap dimensions.
- Raster scaling and canvas-copy behavior reuse the shared Image-buffer transforms of
  ADR-0051. Tileset-specific code and Python orchestration do not implement alternate
  pixel algorithms.
- Rebind and remove are standalone Core Operation Semantics composed by Operation
  Plan through the same packaged Lua handlers. Step results describe execution-time
  facts; a later removal or collection reindex must not invalidate an earlier
  correct result. The final save/reopen gate verifies the completed document.
- Indexed rebinding validates the output Tiles and Transparent Color Index in the
  Effective Palette of each Frame that actually uses those Tiles. It does not
  rewrite Palettes or require the same colors in different valid Frame Palettes.
- SPA does not add a general orphan scanner, automatic garbage collector, or background
  cleanup policy. An Operation can remove only an exact temporary object it created or
  an explicitly addressed unreferenced Tileset.

## Consequences

The [bounded native experiment](../evidence/issue-45-tileset-lifecycle.md) found
actual Tile 0 property loss and broader document changes in the tested resize
paths. Issue #175 retains the intended behavior and native prerequisite; #45 can
complete independently through rebind/remove. Selected property observation under
#41 does not authorize narrowing native metadata preservation.

Changing a Tileset cannot silently reinterpret existing Tile Placements. Broad Grid and
Image effects remain explicit while the Lua Kernel reuses one identity, Raster, and
lifecycle authority.

## Rejected alternatives

- Raw Layer-to-Tileset assignment and deletion-to-Tileset-0 preserve numbers, not Tile
  meaning.
- Image similarity and current Index are not Tile identity.
- Grid is not an ordinary setter because the supported native lifecycle is replacement.
- Automatic resampling or rounding would combine independent authoring decisions.
- A general orphan collector solves no accepted sprite-authoring requirement.
