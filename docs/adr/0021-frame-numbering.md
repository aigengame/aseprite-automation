# ADR-0021: Use Aseprite-aligned public Frame Numbers

## Status

Accepted

## Context

SPA must address Frames consistently across typed requests, Operation Results,
Tags, Cels, exports, and Operation Plans. Aseprite's editor and Lua scripting model
present Frames as one-based values: `Frame.frameNumber` adds one to Aseprite's
internal frame position, and indexed Frame collections accept values beginning at
one. By contrast, Aseprite's native `--frame-range` CLI option accepts zero-based
offsets. Exposing both conventions would force agents to remember which transport
or execution path a field came from and would make equivalent Operations disagree.

The generic word `index` also fails to state whether a value is zero-based or
one-based and whether it is a public animation ordinal or an implementation storage
position.

## Decision

SPA's Published Language uses **Frame Number** for public Frame addressing.

- The schema field is named `frame_number` and its first valid value is `1`.
- A **Frame Range** is inclusive at both endpoints, and both endpoints are Frame
  Numbers.
- Operation-specific range fields and result models state that convention in their
  schemas. They do not expose an unqualified `index` as a Frame address.
- Cels, Tags, Frame inspection, export selection, validation findings, and Plan
  facts report Frames using the same convention.
- The Python adapter or Lua Operation Kernel converts to any zero-based internal or
  native CLI representation. Those values are private execution details and never
  appear as an alternate public convention.

## Consequences

- Agents can copy a Frame Number from inspection into a later request without
  translating it.
- SPA matches the user-visible Aseprite and Lua vocabulary even when a native CLI
  option uses a different offset convention.
- Boundary tests must cover Frame `1`, the last Frame, invalid `0`, inclusive
  single-Frame and multi-Frame ranges, and conversion at any native CLI boundary.
- Implementations may use zero-based positions internally, but public schemas,
  examples, diagnostics, and Operation Results remain one-based.

## Rejected alternatives

### Expose zero-based Frame indexes

This mirrors some internal and CLI mechanics but contradicts Aseprite's editor and
Lua-facing Frame Number and makes inspected values harder to reuse.

### Let each Operation choose its numbering convention

This leaks adapter choices into the Published Language and creates preventable
cross-command ambiguity.

### Use `index` and document the base per field

The name itself omits the semantic distinction SPA needs agents to carry between
calls. `frame_number` makes the public convention explicit and preserves Aseprite's
language.
