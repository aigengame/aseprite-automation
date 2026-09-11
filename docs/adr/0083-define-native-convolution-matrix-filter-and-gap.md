# ADR-0083: Define native Convolution Matrix Filter and report the 1.3.18.5 gap

## Status

Accepted

## Context

Aseprite exposes Convolution Matrix as a native pixel Filter selected through the
`fromResource` script-command parameter. A Convolution Matrix Resource contains its
name, dimensions, center, coefficient data, divisor, bias, and default target
Channels. The native stock loader reads `convmatr.usr`, `convmatr.gen`, and
`convmatr.def` resources through Aseprite's platform resource lookup.

The public script documentation also exposes Filter Channels and Tiled Mode. It says
that custom in-request matrices might be supported in the future; Aseprite 1.3.18.5
accepts only a named stock Resource. SPA has already rejected a generic Filter DSL,
arbitrary convolution request, and alternate image-processing plug-in surface.

Source inspection of Aseprite 1.3.18.5 found two defects at the command boundary:

- the command declares `channels` but never passes it to the Filter manager;
- an unknown `fromResource` name leaves the Filter without a Matrix and the command
  completes as an unreported no-op.

The first defect also prevents headless execution from applying a Resource's default
Channels. UI execution changes the Filter target when a Resource is selected, but
the non-UI branch does not. A real headless probe applied the built-in `brightness`
Resource to RGBA `(10,20,30,40)`. Requests for Red and for Alpha both returned
`(18,28,38,48)`, proving that both the supplied Channels and the Resource's RGB
default were ignored. A missing Resource returned the unchanged pixel with process
success.

Publishing a fixed-all-components subset would not preserve the native Resource's
editor meaning, would make explicit Channels false, and would repeat the partial-
command problem already rejected for other native tools.

## Decision

- `spa filter convolution-matrix` is the intended deterministic pixel Filter
  Operation corresponding to Aseprite's native Convolution Matrix command.
- Its request requires an exact `resource_name`, typed Filter Channels, Tiled Mode
  `none`, `x`, `y`, or `both`, Filter Cels Target, and optional pixel Selection
  Application. It has no Filter Application field and does not mutate Palette
  Entries.
- Runtime resource discovery enumerates Convolution Matrix Resource names and source
  locations in `spa info`, including duplicate-name facts and the Resource's declared
  default Channels. A requested name must match exactly one discovered definition.
  Missing or ambiguous names fail before source mutation with available or conflicting
  Resource facts.
- Resource default Channels are observations for discovery and explanation. They do
  not replace the request's explicit Channels or become ambient behavior.
- RGB accepts non-empty component subsets of `red`, `green`, `blue`, and `alpha`.
  Grayscale accepts `gray` and `alpha`. Indexed support, when proven by a native
  runtime, requires `palette_frame_number` and either RGBA component Channels through
  that Effective Palette and RGB Map or exclusive stored `index` processing.
- Indexed stored-Index output is validated after native execution in the Staged
  Sprite File. Every resulting Index must identify an Entry in its applicable
  Effective Palette. Invalid output fails before Target Commit and reports the Index,
  Palette, Frame, Image, Cel, and pixel location; SPA does not clamp, expand the
  Palette, or switch interpretation.
- Aseprite owns Resource parsing for execution, coefficient precision, Matrix center,
  divisor and bias behavior, transparent-neighbor handling, convolution arithmetic,
  component projection, edge sampling, clamping, Palette lookup, and RGB Map
  quantization. SPA owns explicit resource resolution, request validation, native
  invocation, state restoration, postcondition validation, and structured results.
- The public request accepts no inline coefficients, arbitrary Matrix dimensions,
  caller divisor/bias, generic kernel data, formula, code, or plug-in reference.
  Python and Lua do not implement a second convolution algorithm or generate an
  operation script.
- On Aseprite 1.3.18.5, `spa filter convolution-matrix` has no Operation Descriptor
  and is absent from the Surface Manifest. `spa info` reports a version-specific
  Convolution Matrix Channels Capability Gap with the ignored-parameter,
  Resource-default, and missing-Resource evidence.
- SPA does not publish an implicit all-component, fixed-Resource, RGB-only, or
  reported-success-no-op subset for that runtime.
- A later runtime can publish the Operation after real headless tests prove exact and
  missing Resource handling, every supported Channel combination, Resource default
  independence, all Tiled Modes and edges, Filter Cels Target, Selection, supported
  Color Modes, Indexed Palette validity, Background and Linked Images, rollback,
  restoration, and save/reopen persistence.
- A published Result reports the resolved Resource name and source, declared default
  and effective requested Channels, Tiled Mode, Palette basis where applicable,
  target/Selection and linked Image/Cel facts, changed counts and bounds, and persisted
  before/after content.

## Consequences

- SPA retains the complete intended editor capability without advertising a headless
  command whose Channels cannot be controlled.
- Convolution Matrix Resource discovery becomes agent-visible functional behavior,
  not an implicit dependency on a mutable editor selection.
- A native bug remains a versioned Capability Gap instead of motivating a duplicate
  convolution renderer.
- The candidate can reopen when Aseprite exposes a semantically complete
  non-interactive route.

## Rejected alternatives

### Publish fixed all-component execution

That behavior ignores both the request and the Resource's default Channels and can
produce output different from the editor command represented by the same Resource.

### Accept a missing Resource as a successful no-op

Aseprite's process success does not prove semantic execution. An agent needs a typed
resolution failure rather than an unchanged Sprite presented as success.

### Inherit Resource default Channels

The headless route does not apply them on the tested runtime, and SPA's accepted
Filter contract requires explicit effective Channels.

### Implement convolution in fixed Lua or Python

That would duplicate native arithmetic, transparency, edge, component, and Palette
semantics and violate the accepted single-authority direction.

### Add an inline arbitrary Matrix request

Aseprite 1.3.18.5 does not expose it through the command, and SPA has explicitly
rejected a generic convolution or Filter-extension surface.
