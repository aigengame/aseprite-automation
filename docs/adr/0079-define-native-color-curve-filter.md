# ADR-0079: Define native Color Curve Filter

## Status

Accepted

## Context

Aseprite exposes Color Curve as a native Filter command with a list of Points. Each
Point's X coordinate is an input component value and Y is its output. The current
native curve type is Linear; Spline remains an unimplemented source TODO.

The internal `ColorCurve` sorts added Points by X. A new Point with the same X is
inserted before existing Points at that coordinate, so equal-X order can reverse the
request order and produce a discontinuity whose meaning depends on insertion history.
The public scripting command does not report the resulting order. The editor clamps
manually entered coordinates to the 8-bit `0..255` curve domain.

Native evaluation accepts zero or one Point. Zero Points map every input to zero; one
Point produces a constant output. With multiple Points it uses piecewise integer
linear interpolation, extends the first output to lower inputs and the last output to
higher inputs, then clamps generated values to `0..255`.

Color Curve is not a `FilterWithPalette`: it always processes target pixels. On an
Indexed Sprite it either applies the curve directly to stored indexes or resolves
Palette colors, applies selected RGBA component curves, and maps results through the
active Frame's RGB Map. Index results are clamped to the active Palette's valid size.
The active Frame must therefore become an explicit Palette basis.

## Decision

- `spa filter color-curve` is a deterministic pixel Filter Operation that invokes
  Aseprite's native Color Curve command through one fixed Lua Kernel handler.
- The request requires `points` containing from 1 through 256 objects. Each object has
  integer `input` and `output` in the inclusive range `0..255`.
- Points are supplied in strictly increasing `input` order. Unsorted or repeated input
  values fail preflight; the Kernel does not silently sort, merge, or reorder them.
- Requiring unique integer inputs does not remove an observable 8-bit transfer mapping:
  a step between integer samples can be expressed with adjacent input values. It does
  remove insertion-history-dependent equal-X behavior that Aseprite does not expose as
  a stable command result.
- One Point is the explicit constant-curve form. No fixed first or last Point is
  required. Native evaluation extends the first output below its input and the last
  output above its input.
- The only supported curve type is native `linear`, fixed by the Operation rather than
  carried as a request field. SPA exposes no empty-Point shorthand, Spline, Bézier,
  formula, gamma, arbitrary function, or separate 256-entry lookup-table form.
- RGB accepts non-empty `components` subsets of `red`, `green`, `blue`, and `alpha`.
  Grayscale accepts non-empty subsets of `gray` and `alpha`.
- Indexed accepts exactly one Filter Channels interpretation:
  - `components` uses a non-empty RGBA subset plus required one-based
    `palette_frame_number`; its Effective Palette and RGB Map supply native color
    conversion and quantization.
  - `index` uses required `palette_frame_number`, applies the same native curve to
    stored Palette Indexes, and clamps results to that Effective Palette's valid Entry
    range.
- Color Curve always requires Filter Cels Target and accepts explicit pixel Selection
  Application. It has no Filter Application field and never changes Palette Entries.
- Background Alpha, Filter target eligibility, Linked Image, all-or-nothing mutation,
  state restoration, and persistence rules apply. An Alpha request fails if any target
  is a Background Cel.
- The request accepts no Tiled Mode or hidden editor curve state. The complete Point
  list is the curve authority for the Operation.
- Aseprite remains authoritative for piecewise interpolation, integer arithmetic,
  endpoint extension, output and Index clamping, component projection, Palette lookup,
  and RGB Map quantization. Lua and Python do not evaluate or substitute the curve as
  an alternate mutation algorithm.
- The Operation Result reports the canonical Points, effective Channels, explicit
  Palette basis when applicable, Filter Cels Target and Selection facts, unique Images
  and all affected Cels, changed pixel/index counts and bounds, and persisted
  before/after content observations.
- Delivery requires real-runtime parity for constant, identity, boundary, increasing,
  decreasing, and non-monotonic curves; component and Index paths; every Color Mode;
  Selection, Background and linked targets; rollback; state restoration; and
  save/close/reopen verification.

## Consequences

- Agents receive a compact, exact curve representation without native insertion-order
  surprises.
- Constant, clipped, non-monotonic, and per-channel mappings remain expressible.
- Indexed color and stored-Index interpretations are explicit and use a declared
  Palette basis.
- A future native Spline capability requires its own evidence and contract change.

## Rejected alternatives

### Accept arbitrary Point order and let Aseprite sort it

That would make the effective request differ from the structured input without a
native observation API for the resulting curve.

### Accept repeated input coordinates

Aseprite inserts equal-X Points ahead of existing ones, making their evaluation order
depend on insertion. Adjacent integer inputs express the same observable 8-bit step
without this ambiguity.

### Require identity endpoints

Aseprite supports constant curves and endpoint extension. Mandatory `(0,0)` and
`(255,255)` Points would remove useful native outcomes.

### Publish an empty Point list

One Point already expresses every constant mapping explicitly. An empty list's
all-zero behavior is easier to trigger accidentally and adds no output capability.

### Add Spline, formula, or lookup-table modes

They are not distinct supported inputs of the native Color Curve command. A complete
Point list remains the public curve representation.

### Evaluate the curve in Lua or Python

That would create a second authority for interpolation, integer behavior, Palette, and
RGB Map semantics.
