# ADR-0031: Separate Empty Frame Addition from Frame Duplication

## Status

Accepted

## Context

Aseprite exposes distinct native behaviors for `Sprite:newEmptyFrame()` and
`Sprite:newFrame()`. The first inserts an empty Frame. The second copies a source
Frame and its Cels. Native Cel copying can create independent copies or Linked Cels
according to Layer continuity state, and inserting or removing a Frame adjusts Tag
ranges.

Those behaviors are materially different for an agent. An apparently simple “new
frame” command must not inherit adjacent pixels, duration, Linked-Cel policy, or an
editor background color without saying so.

## Decision

### Empty Frame Addition

- `frame add` inserts a genuinely empty Frame at an explicit one-based position.
- The request supplies `duration_ms` explicitly rather than inheriting an adjacent
  Frame, following ADR-0032.
- Transparent Image and Tilemap Layer intersections remain without Cels.
- If the Sprite has a Background Layer, the Operation creates its required
  full-canvas Cel using an explicit Background Color from the request rather than
  Aseprite's preference-derived background color.

### Frame Duplication

- `frame duplicate` addresses exactly one source Frame and duplicates the whole
  Frame across its Cel-bearing Layers.
- The default insertion position is immediately after the source Frame; a supported
  explicit insertion position remains one-based.
- The request requires `cel_mode: copy | link`. `copy` creates independent Cel/Image
  data; `link` creates native Linked Cels only where Aseprite supports the requested
  relationship. SPA does not consult `Layer.isContinuous` to choose the mode.
- If any Cel cannot satisfy the selected mode, the whole Operation fails before
  Target Commit under the all-or-nothing mutation rule.
- Missing Cels on transparent Layers remain absent. The Background Layer continues
  to satisfy its per-Frame Cel rules.
- Source Frame `duration_ms` is copied unless the request explicitly overrides it.

Both Operations apply Aseprite's native deterministic Frame insertion and Tag Range
adjustment semantics. Their Operation Results report the inserted Frame Number,
renumbered Frames needed by the contract, and every changed Tag Range. `cel copy` and
`cel link` remain the explicit Operations for partial-Layer workflows. Tag playback
properties retain the meanings defined in ADR-0033 while their ranges adjust.

## Consequences

- Empty animation timing and duplicated animation content cannot be confused.
- Linked-Cel behavior is caller intent rather than a hidden Layer property.
- Background fills do not depend on the executing Aseprite profile.
- Whole-Frame and partial-Layer workflows keep separate discoverable Operations.
- Issue #11 owns empty-addition and duplication acceptance.

## Rejected alternatives

### Expose one `frame add` with implicit source behavior

The caller could not know whether it receives an empty timeline position or copied
pixels without understanding a native implementation detail.

### Let `Layer.isContinuous` choose copy versus link

The same request could create different sharing relationships when Layer metadata
changes.

### Inherit duration or Background Color from editor state

Hidden state makes an isolated automation request non-reproducible.
