# ADR-0084: Define native Despeckle Filter

## Status

Accepted

## Context

Aseprite exposes the Despeckle command as a native Median Filter. It independently
sorts values from a rectangular neighboring-pixel window and writes the median of
each selected Channel. Its editor labels include both Despeckle and Median Filter,
while the scripting command is named `Despeckle`.

The public command accepts width, height, Filter Channels, and Tiled Mode. The editor
constrains each dimension to 1 through 100. The scripting path passes raw values to
an implementation that asserts positive dimensions and allocates storage from their
product, so accepting native clamping or unbounded script input would be unsafe and
would diverge from the editor's functional range.

Even dimensions are valid native input. Aseprite anchors a window at
`floor(width/2), floor(height/2)` and selects the sorted element at
`floor(width*height/2)`, which is the upper median for an even sample count. Tiled
Mode controls axis wrapping; `none` repeats edge pixels when a window crosses an
Image boundary.

The Indexed implementation has two branches. Stored-Index processing sorts the raw
Palette Index values. Component processing resolves neighborhood colors through the
Effective Palette, calculates component medians, and quantizes the result through
the RGB Map. In Aseprite 1.3.18.5, however, the component branch incorrectly performs
a second Palette lookup when Green is not selected, causing the unselected Green
component to become zero instead of preserving the candidate pixel's value.

Issue #39 owns the discriminating Indexed probe evidence and feature delivery matrix
for this defect.

## Decision

- `spa filter despeckle` is a deterministic native pixel Filter Operation. SPA keeps
  Aseprite's Despeckle command name and documents its Median Filter behavior; it does
  not introduce a second `median` alias.
- The request requires integer `width` and `height`, typed Filter Channels, Tiled Mode
  `none`, `x`, `y`, or `both`, and Filter Cels Target. It accepts explicit pixel
  Selection Application, has no Filter Application field, and never mutates Palette
  Entries.
- Width and height are each in the inclusive native editor range `1..100`. Missing,
  fractional, non-finite, zero, negative, or larger values fail before invocation
  rather than being clamped or passed to native allocation.
- Odd and even dimensions are valid. The Result reports the effective window anchor
  and sample count. Aseprite's upper-median rule governs even sample counts. A 1-by-1
  request is a valid reported no-op.
- RGB accepts a non-empty component subset of `red`, `green`, `blue`, and `alpha`.
  Grayscale accepts `gray` and `alpha`.
- Indexed requires `palette_frame_number` and exactly one interpretation:
  - `index` sorts stored Palette Index values and writes their native median;
  - `components` resolves colors through that Effective Palette, calculates selected
    RGBA component medians, preserves unselected components, and quantizes through
    the native RGB Map.
- On Aseprite 1.3.18.5, an Indexed `components` set must include `green`. Any non-empty
  Indexed component set without Green reports a version-specific Capability Gap
  before mutation. SPA does not add Green, drop requested Channels, switch to Index,
  repair the result afterward, or invoke another implementation.
- The Indexed Index path validates participating source values against the applicable
  Effective Palette. Its median is one of those input values, and persisted output is
  reread under the normal Palette invariant.
- Background Alpha, target eligibility, Linked Image, all-or-nothing mutation, state
  restoration, and persistence rules apply. An Alpha request fails if any resolved
  target is a Background Cel. A shared Image is filtered once and every affected Cel
  is reported.
- Aseprite owns rectangular neighborhood construction, even-window anchoring, edge
  repetition or Tiled wrapping, per-channel sorting, median selection, transparent
  component behavior, component preservation, Palette lookup, and RGB Map
  quantization. The fixed Lua Kernel owns validation, native mapping and invocation,
  restoration, observation, and the structured result.
- The request accepts no strength, percentile, iteration count, radius, circular or
  shaped window, weighting, color-distance rule, alternate median convention,
  custom statistic, or caller code. Python and Lua do not implement a substitute
  filter or create a generated operation script.
- Results report dimensions, anchor and sample count, median convention, effective
  Channels and Palette basis, Tiled Mode, target/Selection facts, unique Images and
  all affected Cels, changed counts and bounds, applicable Capability Gap facts, and
  persisted before/after content.

## Consequences

- Agents receive Aseprite's complete controllable Despeckle behavior with exact
  window and median semantics.
- The 1.3.18.5 Indexed defect is isolated to its actual Channel combinations instead
  of hiding working RGB, Grayscale, Indexed Index, and Green-containing component
  paths.
- Dimension validation is a functional domain rule derived from the editor and
  native implementation, not a generalized resource-management subsystem.
- Native quantization and edge behavior remain observable rather than reimplemented.

## Rejected alternatives

### Rename the Operation to Median

Despeckle is Aseprite's public command name. Median Filter belongs in its explanation,
not as a competing command vocabulary.

### Require odd dimensions

Aseprite accepts even windows and defines their anchor and upper-median behavior.
Rejecting them would remove a native functional capability.

### Accept arbitrary positive dimensions

The editor's bounded domain is 1 through 100, while the raw scripting path can assert
or allocate disproportionate storage. Passing values outside the editor domain does
not add a supported Aseprite capability.

### Publish all Indexed component combinations

Requests without Green silently corrupt an unselected component on the tested
runtime and therefore cannot satisfy the explicit Channel contract.

### Add Green automatically

That would change the requested mutation and conceal the native defect.

### Implement another median filter

That would duplicate neighborhood, edge, median, transparency, and Palette semantics
and violate the fixed native-operation authority.
