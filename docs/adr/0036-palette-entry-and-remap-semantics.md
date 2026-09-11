# ADR-0036: Separate Palette Entry edits from Remap Colors

## Status

Accepted

## Context

An Indexed Image stores Palette Indexes rather than RGBA colors. Aseprite's Palette
entry setters and resize operation change the Palette but do not rewrite those pixel
indexes. Consequently, changing an Entry's RGBA color intentionally recolors every
applicable pixel that stores its index, while reordering entries without remapping
pixels changes their rendered colors unintentionally in many workflows.

Aseprite treats **Remap Colors** as a separate action. Its remap rewrites Indexed
pixels through an index mapping and adjusts the Transparent Color Index. Native
helpers can search for exact or nearest colors, but an implicit nearest-color choice
would make agent output depend on behavior that was not present in the request.

Palette shrink is also structural. If removed indexes remain in Images, their stored
values no longer name valid Palette Entries. Silently clamping them, selecting a
nearest color, or moving transparency would corrupt authored intent.

## Decision

- A **Palette Entry** is a zero-based Palette Index paired with an RGBA color.
- `palette set` changes declared Entry colors in an exact Palette Change and does not
  rewrite Indexed pixel values. Recoloring applicable pixels is its intended result.
- `palette reorder` is an atomic agent-facing Operation: it reorders Entries and
  applies the exact corresponding old-to-new index mapping to the Indexed Images
  selected by its Palette Reorder Scope so resolved RGBA colors remain stable. Its
  scope and linked-Image rules are defined by ADR-0037.
- `palette remap` accepts an explicit old-to-new Palette Index mapping and follows
  Aseprite's Sprite-wide Remap Colors semantics for Indexed Images and the
  Transparent Color Index. It does not infer a nearest color or depend on editor
  preferences. ADR-0037 defines its target and validity rules.
- Palette growth requires an explicit RGBA color for every appended Entry.
- Palette shrink resolves all applicable Indexed Images before mutation. If a pixel
  uses an index that would be removed, or the Transparent Color Index would be
  removed, the Operation fails without a Target Commit. The caller performs an
  explicit remap before shrinking.
- Results report the exact Entry or index mapping, resulting Palette Change and
  effective Frame Range, all affected Images, Cels, and Frames, and the old and new
  Transparent Color Index where it changes.
- These semantics are owned by the Palette domain and implemented in the Lua
  Operation Kernel. They are not a generic migration or consistency subsystem.

## Consequences

- Agents can choose deliberately between recoloring a sprite and preserving its
  rendered colors while reorganizing its Palette.
- Destructive structural changes cannot leave out-of-range pixel or transparency
  indexes.
- Remap requests and results are deterministic and independently verifiable.
- Tests distinguish Palette-only mutation from pixel remap and verify the persisted
  Palette, Images, and transparency after save and reopen.

## Rejected alternatives

### Add a generic `preserve` boolean to every Palette mutation

The flag would obscure whether the Operation changes Entries, pixels, transparency,
or all three. Separate domain Operations state the behavior directly.

### Make every Palette edit remap pixels automatically

That prevents the common and intentional act of recoloring indexed artwork by
changing an Entry value.

### Preserve indexes for Palette Reorder

The operation name expresses structural organization. Preserving indexes would
change rendered colors and duplicate what explicit Entry replacement can already do.

### Choose nearest surviving colors during shrink

The result would be lossy and depend on a policy absent from the request.

### Leave removed indexes in Images

This creates invalid Palette references and makes rendering or later conversion
dependent on undocumented fallback behavior.
