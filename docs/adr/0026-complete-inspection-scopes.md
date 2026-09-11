# ADR-0026: Make inspection scope and completeness explicit

## Status

Accepted

## Context

An agent must distinguish a Sprite with no Cels from a result that did not inspect
Cels, and an unsupported Aseprite capability from a supported capability whose
collection is empty. Large pixel and Tilemap observations also need bounded forms,
but silently truncating a successful result would make later mutation and validation
decisions unsafe.

Inspection shapes differ materially across Sprite structure, Images, Palettes,
Tilesets, Tilemaps, Slices, and other Aseprite concepts. Making their facts explicit
does not require a universal query language, cursor protocol, or Observation model.

## Decision

- Each inspection Operation owns a typed **Inspection Scope** made from its native
  sections, objects, Frame Ranges, Rectangles, or other domain-specific fields.
- Its Operation Result reports the normalized scope actually evaluated and explicitly
  identifies optional sections that were not requested.
- A successful inspection is complete for that normalized scope. SPA never silently
  truncates, samples, or omits promised facts.
- Within an inspected section, an empty native collection is represented as `[]`.
  A single optional native relationship uses `null` only when its schema defines
  native absence as that value. Neither representation means not requested.
- If the caller requests a capability unsupported by the installed Aseprite version,
  the Operation returns a typed Failure Envelope rather than partial success.
- If a request exceeds an Operation's Domain Bound, it fails with typed details that
  report the applicable allowed range.
- A domain can define explicit window, chunk, page, or Artifact projections. A
  successful windowed result reports exact **Inspection Coverage** and whether the
  broader traversal is complete.
- Coverage fields and continuation inputs remain operation-specific. SPA does not
  define a universal cursor, Observation Envelope, or Inspection Result base class.

## Consequences

- Agents can distinguish native absence, not requested, unsupported, and too large
  without interpreting warning text.
- Inspection output remains bounded without making a partial response look complete.
- Operations can choose the projection natural to their data, including a Rectangle
  for pixels, a Tile Cell region, a Frame Range, or a validated Artifact.
- Result schemas and tests must define completion relative to the normalized scope.

## Rejected alternatives

### Return as much data as fits and add a warning

This turns a successful result into ambiguous partial evidence and requires agents to
parse diagnostics before trusting typed fields.

### Use empty values for sections that were not inspected

An empty collection is a meaningful native observation and cannot also mean omitted.

### Introduce one pagination and observation framework

Pixel rectangles, Frame ranges, Layer trees, Palette entries, and Tilemap chunks do
not share enough traversal semantics to justify a cross-domain protocol.
