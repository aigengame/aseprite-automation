# ADR-0049: Model Tileset Grid change as replacement-style resize

## Status

Accepted

## Context

In Aseprite 1.3.18.5, `Tileset.grid` is readable but has no Lua setter. The editor's
Tileset selector enables Grid width and height for a new Tileset and disables them
for an existing one. Native Sprite resizing changes tile size by constructing a new
Tileset, transforming its Tile Images, and replacing the original Tileset rather
than mutating a Grid field.

A Grid change affects every Tile Bitmap and every referencing Tilemap Layer's
effective Grid and Canvas coverage. Exposing it as a field of ordinary `tileset set`
would misrepresent the Aseprite object lifecycle and hide a broad content mutation.
Treating it as permanently unsupported would also omit an agent-useful workflow that
can be built from supported Tileset construction, rebinding, and removal semantics.

## Decision

- `tileset set` does not accept `grid`. A concrete Tileset Grid is not an ordinary
  writable property in SPA's supported Aseprite contract.
- SPA defines `spa tileset resize` as a replacement-style lifecycle Operation.
- Its fixed Lua Kernel handler constructs a replacement Tileset with the requested
  Grid, transforms and preserves every non-empty Tile Image, Tile Key, data, and
  other accepted Properties under explicit resize policies, rebinds every
  referencing Tilemap Layer, and removes the old Tileset in one all-or-nothing
  Mutation.
- The handler reuses the Core Operation Semantics of `layer set-tileset` and
  `tileset remove`; Python does not recreate them or generate temporary Lua.
- The result identifies the old and replacement Tileset facts, complete Tileset
  Index changes, every resulting Layer relationship, and affected Tile/Cel facts.
  It does not claim that a persistent Tileset identity survived replacement.
- Tile Image transformation and Tilemap spatial policies are part of the named
  resize contract and require a separate accepted decision plus a real Aseprite
  vertical slice before the candidate ships.
- `sprite resize` remains a distinct Sprite-level Operation. Any Tileset scaling it
  performs belongs to that explicit Sprite operation and is never a hidden side
  effect of `tileset set`.

## Consequences

- Public contracts match Aseprite's construction-time Grid model.
- Agents receive a direct Grid-change workflow without unsafe private mutation or
  Python-owned semantics.
- The broad Tile and Tilemap effects are named, policy-driven, and verifiable.
- Existing lifecycle handlers remain the semantic authority used by the composite.

## Rejected alternatives

### Add `grid` to `tileset set`

The supported Lua API has no setter, and the field shape would conceal replacement,
Tile Image conversion, and Layer coverage changes.

### Report every Grid change as a permanent Capability Gap

The functional workflow can be implemented through supported public construction,
Tile editing, Layer rebinding, and Tileset removal seams.

### Let `sprite resize` change a Tileset implicitly

Sprite scaling has its own scope and policies. It cannot serve as an unreported
Tileset lifecycle mechanism.

### Implement replacement semantics in Python

That would violate the Lua Kernel's authority over Core Operation Semantics and
duplicate the accepted lifecycle behavior.
