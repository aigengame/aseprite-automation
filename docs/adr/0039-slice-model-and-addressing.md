# ADR-0039: Preserve Slice Keys and use snapshot-relative Slice addressing

## Status

Accepted

## Context

Aseprite models a Slice as a named Sprite-contained object with ordered
`SliceKey` values and user data. Each Key starts at a Frame and contains bounds,
an optional center Rectangle, and an optional pivot Point. The `.aseprite` Slice
chunk persists the name and Keys but no object ID. Flattening this model into one
Rectangle would lose animation metadata needed by UI and engine export workflows.

The public Lua collection `Sprite.slices` is one-based. Native `Slices::add()`
inserts a new Slice at the front, so collection position can change. Aseprite
permits duplicate Slice names, and native name lookup returns the first match.
The Lua Slice API exposes no ID or UUID. Agents nevertheless need deterministic,
inspectable target semantics without SPA creating a parallel identity system.

## Decision

- A Slice owns its name, user data, and complete ordered collection of explicit
  Slice Keys. SPA does not reduce a multi-key Slice to one static Rectangle.
- Each Slice Key uses public one-based `frame_number`. Its `bounds` are in Canvas
  Pixel space. Optional `center` and `pivot` coordinates are relative to the
  Slice Bounds, matching Aseprite's native model.
- A Key's inclusive effective Frame Range starts at its Frame and ends at the
  Frame before the next Key, or at the Sprite's last Frame. SPA makes no
  synthetic Key effective before the first explicit Key.
- `slice list` and `slice get` return current `slice_index`, complete Slice
  properties, every explicit Slice Key, and each Key's effective Frame Range.
- An Operation targeting an existing Slice accepts exactly one of current
  one-based `slice_index` or `slice_name`. A name must match exactly one Slice;
  zero matches fail as not found and multiple matches fail as ambiguous.
- `slice_index` is a current-snapshot address, not a Persistent Identity. A
  successful mutation rereads and returns the resulting Slice and current index.
- SPA exposes no process-local native object ID and assigns no Slice UUID or SPA
  Key. Slice resolution remains operation-specific and creates no universal
  Selector or Locator abstraction.
- This decision defines the persisted model, inspection contract, and addressing.
  Which Slice Key lifecycle mutations are reachable through the supported
  Aseprite runtime seam is decided separately from the model itself.

## Consequences

- Agents retain exact Frame-varying Slice metadata needed for nine-slice,
  pivot-based, and export workflows.
- Index-based requests are deterministic for one inspected snapshot but callers
  must refresh after structural changes such as insertion or removal.
- Duplicate names remain valid Aseprite data without introducing hidden
  first-match mutations.
- Implementations must normalize native zero-based storage or exporter Frame
  values to public one-based Frame Numbers.
- Issue #40 owns Slice model and addressing acceptance.

## Rejected alternatives

### Flatten each Slice into one static Rectangle

This discards native timeline semantics and makes inspection insufficient to
verify or preserve existing documents.

### Expose an internal Slice object ID

The Lua API does not expose one and the `.aseprite` Slice chunk does not persist
one, so it cannot serve as a cross-Operation identity.

### Persist a synthetic Slice UUID or SPA Key

Current Slice workflows are addressable by an inspected index or unique name.
Adding metadata and lifecycle rules would create a parallel identity system
without an accepted functional requirement.

### Select the first matching Slice name

That copies a native convenience behavior but makes mutation depend on hidden
collection order when duplicate names exist.

### Introduce a universal Selector

Slice addressing has a small operation-specific solution and does not justify a
cross-domain query language.
