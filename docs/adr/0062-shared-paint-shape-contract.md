# ADR-0062: Share explicit Rectangle and Ellipse Paint semantics

## Status

Accepted

## Context

Aseprite provides separate `rectangle`, `filled_rectangle`, `ellipse`, and
`filled_ellipse` editor tools. The outline tools can have optional-fill state, and
their two mouse Points use inclusive geometry. SPA uses half-open Rectangles and must
not inherit fill or keyboard modifier state.

Rectangle and Ellipse share targeting, Brush, Ink, clipping, Selection, and result
rules while retaining independent native tools and delivery evidence.

## Decision

- Paint Shape is the shared request contract for `spa paint rectangle` and
  `spa paint ellipse`.
- It requires a positive half-open `bounds` Rectangle in Image Pixel space and a
  `style` of `outline` or `filled`.
- It also requires Standard Paint Brush, compatible Color Value, integer opacity in
  `0..255`, an accepted Ink, clipping behavior, and optional explicit Selection
  Application under the existing Paint contracts.
- The Kernel converts bounds to inclusive native Points `(x,y)` and
  `(x+width-1,y+height-1)`.
- Rectangle outline and filled styles invoke `rectangle` and `filled_rectangle`.
  Ellipse outline and filled styles invoke `ellipse` and `filled_ellipse`.
- Native Tool Invocation explicitly controls and restores any optional-fill state
  used by outline tools.
- A width or height of 1 retains the native selected shape's degenerate output. The
  operation does not substitute Paint Line.
- Outline and filled tools use the declared Standard Brush. Bounds refusal, explicit
  clipping, and reported coverage reflect the rendered Brush footprint, which can
  extend beyond geometric bounds.
- No proportional constraint, from-center behavior, rotation, or keyboard modifier
  is implicit. Such geometric intents require typed request fields and native
  validation before delivery.
- Native execution cannot create a Cel, expand its Image, move it, or break links.
- Existing ordinary Image and Background Cels are supported subject to the opaque
  Background postcondition. Reference, Tilemap, absent, and non-Cel targets fail.
- Linked Image sharing is preserved and results enumerate every affected Cel.
- Results return shape kind, style, requested bounds, native endpoint mapping,
  normalized Brush/Ink/opacity, actual affected region, pixels clipped or excluded by
  Selection, changed count, every affected Cel/link, and before/after content digest.
  Save/close/reopen verifies persisted facts.
- Rectangle and Ellipse have independent real `aseprite --script` editor-parity
  delivery gates. Failure yields that shape's typed Capability Gap without changing
  the other or falling back to GraphicsContext or Python geometry.

## Consequences

- Rectangle and Ellipse expose consistent agent inputs without merging native tools.
- Half-open public geometry has an explicit inclusive-native conversion.
- Fill style and modifier behavior cannot leak from editor preferences.
- A defect in one shape's native path does not misreport the other shape's capability.

## Rejected alternatives

### Expose four unrelated public contracts

They would duplicate Brush, bounds, Selection, clipping, and result semantics.

### Use one outline tool and toggle hidden fill state

Aseprite already supplies explicit filled tool IDs, while hidden state would make the
same request non-deterministic.

### Rewrite degenerate shapes as lines or points

The native shape tools define their own one-pixel geometry and Brush behavior.

### Fall back to GraphicsContext

That would change the accepted editor-tool pixel authority.
