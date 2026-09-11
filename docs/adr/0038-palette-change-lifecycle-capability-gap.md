# ADR-0038: Report the Palette Change lifecycle capability gap

## Status

Accepted

## Context

ADR-0035 originally treated Palette Change creation and deletion as explicit SPA
lifecycle Operations. Source and scripting API inspection of Aseprite 1.3.18.5
invalidated the implementation premise behind that decision. Issue #30 owns the
runtime evidence and delivery acceptance for this feature boundary.

`Palette.frame` and `Palette.frameNumber` are read-only in Lua. `Sprite:setPalette`,
`Palette:setColor`, `Palette:resize`, and the public palette commands modify the
Palette already effective at a Frame; they do not add a new change point. Lua exposes
no `Sprite:newPalette` or `Sprite:deletePalette`. Aseprite has an internal C++
`AddPalette` command used by decoding and import paths, but it is not a public Lua or
editor command. The `.aseprite` format persists multiple Palette Changes, so SPA must
still inspect and edit them when they already exist.

Calling internal C++, patching binary file chunks, or synthesizing an indirect import
workflow would violate the fixed Lua Operation Kernel boundary and could not be
described as supported Aseprite automation behavior.

## Decision

- SPA does not publish `palette add` or `palette remove` for Aseprite 1.3.18.5.
- Palette inspection continues to list existing Palette Changes and resolve Effective
  Palettes. Entry mutation, resize, import, reorder, and export can address an exact
  existing `palette_frame_number` according to their accepted semantics.
- Requesting a missing `palette_frame_number` fails as not found; an entry mutation
  never creates a Palette Change implicitly.
- `spa info` reports Palette Change creation/deletion as an unavailable scripting
  capability for the detected runtime, with a stable reason distinct from a runtime
  discovery failure.
- The installed Surface Manifest contains no add/remove descriptors while the gap
  remains. Documentation names the gap rather than presenting candidate commands.
- SPA does not use private C++ APIs, direct `.aseprite` binary editing, generated
  ordinary-operation Lua, or import side effects to simulate the lifecycle.
- A future supported Aseprite public API or editor command, followed by a real
  save/close/reopen prototype, can justify a new decision that adds the Operations.

## Consequences

- The Palette model accurately represents documents that SPA can read even when SPA
  cannot create every native persisted shape through the supported runtime seam.
- Agents can discover the limitation structurally before planning an edit.
- Functional breadth remains evidence-driven instead of becoming a claim that the
  Lua Kernel cannot fulfill.
- ADR-0035's earlier Palette Change lifecycle clause is superseded by this decision.

## Rejected alternatives

### Keep candidate add/remove commands without an implementation seam

Their presence would advertise a product capability that cannot pass an installed
end-to-end slice.

### Call Aseprite's internal C++ command

It is not reachable through the supported public Lua/editor contract and would bind
SPA to private implementation details.

### Patch Palette chunks in the `.aseprite` file

This would create a second document engine outside the Lua Operation Kernel and risk
corrupting data that Aseprite owns.

### Manufacture a change point through an import detour

An indirect file-import side effect is not a deterministic Palette lifecycle
operation and would broaden mutation far beyond the requested object.

### Treat the gap as a permanent product prohibition

The decision is tied to tested Aseprite capability evidence. A supported native seam
can reopen it without changing the domain model.
