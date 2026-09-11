# ADR-0030: Encode Selection as normalized binary runs

## Status

Accepted

## Context

Aseprite's native Selection Mask stores one binary fact per Canvas Pixel: selected or
not selected. SPA must serialize arbitrary Selection shapes without depending on an
open Document, while keeping empty and all-canvas intent explicit and making results
stable to compare.

Keeping rectangles, ellipses, polygons, color searches, and prior set operations as
variants of the stored value would preserve construction history instead of the
resulting native Mask. A PNG can visualize a Mask but does not naturally carry its
Canvas origin, and importing it would require pixel format, alpha threshold, and
color interpretation rules.

## Decision

The canonical Selection Encoding is a discriminated union:

- `empty` represents zero selected pixels.
- `all` carries the exact Canvas Rectangle whose pixels are selected.
- `mask` carries tight half-open `bounds` and ordered rows. Each row contains an
  absolute Canvas Pixel `y` and sorted `{x, length}` runs of selected pixels.

For `mask`, lengths are positive integers; rows and runs are sorted; runs do not
overlap; adjacent runs are merged; every run lies within `bounds`; and `bounds` has
no unselected outer row or column. This normalization gives the same binary pixel set
one public representation.

Rectangle, ellipse, polygon, by-color, and other construction forms belong to
`selection create` requests. Selection Operations return the normalized binary
result rather than construction history.

Inline Selection values are subject to the owning Operation's Domain Bound. A JSON
Artifact with role `selection-mask` contains the same canonical schema for larger
values. It is not a separate file-only model. A PNG can be emitted as a Preview
Artifact for human review but is not authoritative or assumed reversible.

The Lua Operation Kernel owns decoding, normalization, native Selection
materialization, and result encoding for both inline and Artifact inputs. Python
validates public shape and statically decidable invariants without reimplementing
Mask behavior.

## Consequences

- Arbitrary binary Selections are lossless, deterministic, and independent of image
  color or alpha semantics.
- Agents can compare, cache, and reuse normalized values across Operations.
- Empty, all-canvas, and arbitrary Mask cases are explicit without overloading an
  absent request field.
- Large Selection transport does not require a second schema.
- Tests cover canonical ordering and merging, tight bounds, invalid runs, inline and
  Artifact parity, native pixel equality, and non-authoritative previews.

## Rejected alternatives

### Store construction geometry as the Selection value

Different operation histories can produce the same native binary Mask, and arbitrary
Selections cannot always be reduced to a convenient geometric primitive.

### Use PNG as the authoritative Selection

PNG introduces origin, color, alpha, and threshold interpretation that the native
binary Mask does not need.

### Store every selected coordinate independently

This is easy to describe but creates needlessly large agent payloads for common
contiguous selections and lacks a natural canonical grouping.
