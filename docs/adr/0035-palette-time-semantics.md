# ADR-0035: Preserve the Palette model and mutation boundaries

## Status

Accepted

This ADR consolidates the durable cross-feature decisions from ADR-0036 and
ADR-0037. Issues #30 and #31 own exact planned feature contracts, acceptance,
evidence requirements, provenance links, curated evidence summaries, and
runtime-specific candidate-gap handling. Tests and evidence artifacts own executed
proof; the installed Surface Manifest owns installed Capability Gaps.

## Context

Aseprite stores Frame-based Palette change points. An Effective Palette remains
active until the next change. Indexed Images store Palette Indexes rather than
resolved RGBA values, and the Transparent Color Index belongs to the Sprite.
Changing an Entry, remapping indexes, and reordering Entries therefore have
different effects on Images, Frames, and linked Cels.

## Decision

- A **Palette Change** begins at one-based `palette_frame_number`. The
  **Effective Palette** at a Frame is the latest change at or before it.
- Palette mutation targets an exact existing change point and reports its
  affected effective Frame Range. It does not manufacture a missing Palette
  Change.
- A Palette Entry is a zero-based Palette Index and an RGBA value. The starting
  Frame identifies a Palette Change; collection position, process-local ID, and
  synthetic identity do not.
- Entry color edits do not rewrite Indexed pixels. Recoloring pixels that store
  the edited index is their intended effect.
- **Remap Colors** accepts an explicit index mapping and preserves Aseprite's
  Sprite-wide scope, including Indexed Images and the global Transparent Color
  Index.
- Palette reorder preserves rendered colors through an explicit mapping and
  declared Palette-change or Sprite scope. It does not silently broaden its
  target or unlink shared Cels.
- Growth supplies every new Entry value. Shrink does not clamp, choose nearest
  colors, or leave invalid indexes; unsupported removal fails until an explicit
  remap makes it valid.
- Runtime-specific Palette Change lifecycle availability is reported through
  the installed Surface Manifest and Capability Gaps, not simulated with
  private APIs or file patching.

## Consequences

Agents can distinguish the requested Frame, supplying change point, and
affected range. They can deliberately choose recoloring, index remapping, or
render-preserving organization without hidden changes to pixels,
transparency, or Cel sharing.

## Rejected alternatives

One independent Palette per Frame duplicates native shared state. Implicit
nearest-color or scope expansion is lossy. A generic consistency service or
synthetic Palette identity adds machinery without matching Aseprite's model.
