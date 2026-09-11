# ADR-0040: Expose complete Slice reads and report the Slice Key mutation gap

## Status

Accepted

## Context

ADR-0039 requires complete inspection of every explicit Slice Key. Aseprite 1.3.18.5
persists that model, but its public Lua surface does not provide complete arbitrary
Slice Key mutation. Issue #40 owns the runtime evidence and delivery acceptance for
this feature boundary.

The native `ExportSpriteSheet` command can emit every Slice and Key when
`listSlices` is enabled. It is callable non-interactively from Lua and can therefore
serve as an Aseprite-owned observation primitive. In contrast, the editor's
`SliceProperties` command requires UI availability, and the underlying C++
`SetSliceKey` command is not a public scripting API.

Whole-Slice lifecycle remains reachable through `Sprite:newSlice()` and
`Sprite:deleteSlice()`. Name and user data are Slice-level properties. Public Lua can
also safely change geometry for the exact shape it addresses: one Slice Key at
native Frame 0, which SPA publishes as Frame 1. Applying those setters to a multi-Key
or later-starting Slice would silently target a different timeline value than an
agent could intend.

## Decision

- `slice list` and `slice get` provide the complete model required by ADR-0039.
  Their fixed Lua Operation Kernel handler invokes native `ExportSpriteSheet` with
  `listSlices`, reads the resulting private vendor JSON, verifies its required
  shape, converts native zero-based Frames to public one-based Frame Numbers, and
  constructs a fresh Kernel Response.
- The exporter JSON and any required texture are temporary data artifacts inside
  the invocation workspace. They are neither public Artifacts nor executable Lua.
- Python owns process execution, temporary workspace lifecycle, Kernel Protocol
  transport, and schema validation. It does not parse vendor Slice metadata into
  public semantics or implement another Slice inspection path.
- SPA supports whole-Slice creation with one explicit initial Key at Frame 1,
  whole-Slice deletion, rename, and user-data mutation through fixed Lua handlers.
- SPA permits `bounds`, `center`, and `pivot` mutation only when inspection proves
  that the target has exactly one explicit Key at Frame 1. A multi-Key Slice or a
  Slice whose sole Key begins later fails before mutation.
- Aseprite 1.3.18.5 has a Capability Gap for arbitrary Slice Key creation,
  mutation, and deletion. The Surface Manifest publishes no `slice key add`,
  `slice key set`, or `slice key remove` descriptors, and `spa info` reports the
  gap for that runtime.
- SPA does not automate the UI-only `SliceProperties` command, call private C++
  commands, patch `.aseprite` chunks, move Slice Core Operation Semantics into
  Python, or generate ordinary-operation Lua to simulate support.
- A future public, non-interactive Aseprite API followed by real multi-Key
  save/close/reopen validation can justify reopening the Capability Gap.

## Consequences

- Agents can inspect and preserve existing multi-Key Slices even though the tested
  runtime cannot automate their full mutation lifecycle.
- The native exporter extends observation without creating a second semantic
  authority: normalization stays in the fixed Lua Kernel handler.
- Static Slice workflows can create and edit geometry, while ambiguous timeline
  mutations fail without a Target Commit.
- Runtime discovery communicates the unsupported mutation surface before an agent
  constructs a Plan.

## Rejected alternatives

### Let Python normalize native Slice exporter JSON

That would move Core Operation Semantics outside the Lua Operation Kernel and create
a second implementation path for Slice inspection.

### Use the Lua Slice properties for every Slice

They expose the first Key and write native Frame 0. On a multi-Key or later-starting
Slice, that behavior cannot express an arbitrary intended Key and can alter timeline
meaning.

### Drive the Slice Properties window

The command is UI-only and SPA explicitly excludes editor GUI automation and hidden
active-editor state.

### Call the private C++ SetSliceKey command or patch the file

Neither is part of the supported public automation seam. Both would couple SPA to
private document-engine details outside its fixed Lua boundary.

### Advertise key commands and fail only when invoked

Publishing descriptors would claim support that the tested runtime cannot provide.
The structured Capability Gap communicates the limitation without a false command
surface.
