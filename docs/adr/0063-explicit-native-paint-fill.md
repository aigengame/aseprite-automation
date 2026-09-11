# ADR-0063: Make native Paint Fill inputs explicit

## Status

Accepted

## Context

Aseprite's `paint_bucket` tool uses one seed Point and native flood-fill behavior.
`app.useTool` accepts tolerance and contiguous mode, but Refer To, Stop at Grid, and
Pixel Connectivity are read from Paint Bucket preferences. Leaving those preferences
implicit would make an identical SPA request produce different pixels.

All Layers matching and Stop at Grid are useful Aseprite editing capabilities. They
should remain available to agents without importing GUI visibility or active-editor
state into the public contract.

## Decision

- `spa paint fill` invokes Aseprite's fixed `paint_bucket` tool from one Image Pixel
  `seed` through Native Tool Invocation.
- The request requires a compatible Color Value, integer `opacity` and `tolerance`
  in `0..255`, an accepted Ink, explicit `contiguous`, Refer To as `active-layer` or
  `all-layers`, and boolean `stop_at_grid`.
- Paint Fill does not accept a Brush.
- A contiguous request requires Pixel Connectivity as `four-connected` or
  `eight-connected`. A non-contiguous request forbids connectivity because native
  Aseprite ignores it in that mode.
- `active-layer` means the explicitly addressed target Layer, not the active editor
  Layer.
- `all-layers` uses Aseprite's native visible-Layer composite for the addressed Frame
  as the matching source and writes only the addressed target Cel.
- Tolerance retains Aseprite's native comparison for the Sprite Color Mode. SPA does
  not redefine it as perceptual distance or convert Color Modes implicitly.
- `stop_at_grid: false` maps to native `NEVER`. `true` maps to native `ALWAYS` and
  uses the persisted Sprite Grid to constrain the fill to the cell containing the
  seed.
- SPA does not use native `IF_VISIBLE`: GUI grid visibility is not an input, and the
  explicit boolean selects the same two resulting behaviors directly.
- The fixed Lua Kernel sets and restores Refer To, Stop at Grid, and Pixel
  Connectivity around `app.useTool`. Tolerance and contiguous mode are supplied
  directly. No Python or generated Lua implements flood-fill semantics.
- Existing Paint clipping and explicit Selection Application apply. Native execution
  cannot create a Cel, expand an Image, move a Cel, or break links.
- Existing ordinary Image and Background Cels are supported subject to the opaque
  Background postcondition. Reference, Tilemap, absent, and non-Cel targets fail.
- Linked Image sharing is preserved and the Image is filled once.
- Results return the seed, normalized color/opacity/Ink/tolerance, Refer To and source
  scope, contiguous mode and applicable connectivity, Stop at Grid and its exact
  effective Grid cell, requested and actual affected regions, pixels clipped or
  excluded by Selection, changed count, every affected Cel/link, and before/after
  content digest. Save/close/reopen verifies persisted facts.
- Issue #27 owns the feature delivery matrix and real-runtime acceptance evidence.

## Consequences

- Agents can select every result-distinct native Paint Bucket behavior without hidden
  editor state.
- Native Aseprite remains the authority for color matching, visible-Layer rendering,
  connectivity, Grid boundaries, and pixel application.
- Conditional GUI visibility is removed from automation inputs without removing an
  achievable Paint Bucket result.
- Request validation rejects options that native execution would silently ignore.

## Rejected alternatives

### Inherit Paint Bucket preferences

Identical requests would vary with Refer To, connectivity, and Grid preferences.

### Expose native `IF_VISIBLE`

It chooses `NEVER` or `ALWAYS` from GUI state and adds no distinct result behavior.

### Accept connectivity for non-contiguous mode

Native Aseprite ignores it, which would make the public request misleading.

### Implement flood fill in Lua or Python

That would create a second authority for a core Aseprite editing semantic.
