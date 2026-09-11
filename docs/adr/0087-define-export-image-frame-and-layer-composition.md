# ADR-0087: Define Export Image Frame and Layer Composition

## Status

Accepted

## Context

Aseprite can export the persisted visible Layer composition, make all Layers visible,
include named Layers or Groups, and ignore selected Layers. Its native renderer owns
stacking, Blend Mode, Layer and Cel opacity, Background, Tilemap, and Reference Layer
behavior.

The CLI expresses Layer filtering with names, paths, and wildcard-like filters. The
editor and parts of the scripting command can instead inherit the active Frame,
active Layer, or current timeline Range. Those ambient inputs are unsuitable for a
typed agent request, and duplicate Layer names make an unqualified name insufficient.

Aseprite's own `RestoreVisibleLayers` implementation demonstrates the supported
rendering seam: it temporarily applies an expanded selected-Layer visibility set,
renders through the native pipeline, and restores every changed visibility flag.
Selecting a Group propagates to its descendants; selecting a child requires its
ancestor path to be visible. SPA can use the same public Layer properties and native
export renderer through a fixed Lua handler without implementing compositing.

Still-image export also needs a precise Frame boundary. Allowing a Tag or Frame Range
would make output cardinality depend on format and filename behavior and would
overlap the distinct GIF, Sheet, and Sequence operations.

## Decision

- `spa export image` requires exactly one public one-based `frame_number`. It never
  inherits the active Frame or current timeline Range and accepts no Tag, Frame
  Range, Playback Context, or `ignore_empty` input.
- The request requires one discriminated Layer Composition:
  - `visible` renders the Sprite's persisted effective visible-Layer hierarchy and
    can exclude a unique set of exactly addressed Layers;
  - `all` renders all natively renderable Layers regardless of persisted visibility
    and can exclude a unique set of exactly addressed Layers;
  - `include` renders a non-empty unique set of exactly addressed Layers.
- All addresses use the accepted Layer-specific addressing contract. Names must be
  unique where used; indexes and UUIDs retain their defined meaning. The public
  request accepts no glob, path pattern, active Layer, selected Layer, or `app.range`
  dependency.
- Including a Group expands to its complete descendant subtree. Excluding a Group
  excludes that complete subtree. Including a child makes the required ancestor
  Groups visible for rendering without independently adding their unrelated
  descendants. The Result reports requested addresses, exclusions, Group expansion,
  required ancestors, and the final effective render set in native stack order.
- Explicit inclusion can render a persistently hidden Layer. `all` can render hidden
  Layers. `visible` remains governed by persisted effective hierarchy visibility
  before its explicit exclusions.
- Before rendering, the fixed Lua Kernel resolves the complete Layer set and records
  every visibility value it must change. It applies temporary visibility, invokes
  the native renderer/exporter for the selected Frame, and restores all values on
  success and every handled failure path. The Source Sprite File is not saved or
  mutated by the Export Operation.
- Aseprite owns compositing order, group behavior after expansion, Blend Modes,
  Layer/Cel opacity, Background, Tilemap, Reference Layer, color, and pixel rendering.
  Lua owns exact target resolution, temporary native state, invocation, restoration,
  observation, and structured facts. Python owns neither visibility semantics nor
  compositing.
- The Operation combines this Frame and Layer Composition with the accepted Export
  Image Area and Export Destination. It always produces exactly one static raster
  Artifact. Animated playback and multiple output Frames belong to `export gif`,
  `export sheet`, and `export sequence`.
- Rendering the Frame, Layer Composition, and Export Image Area is the first step of
  the fixed `export image` order defined by ADR-0094. Later Color Profile, Palette,
  Color Mode, transparency, and encoding steps operate only on that disposable result.
- Issue #7 owns the first File Format delivery matrix and real-runtime acceptance
  evidence; later format issues reuse this decision without inheriting support claims.

## Consequences

- Agent requests preserve Aseprite's visible, all, include, and ignore capabilities
  without depending on interactive selection state.
- Exactly one Frame makes `export image` output cardinality and verification stable
  across supported static formats.
- Aseprite remains the sole compositing authority; SPA controls only the explicit
  inputs needed to reach the requested native composition.
- Group expansion and actual rendered Layers become observable result facts instead
  of implicit filename-filter behavior.

## Rejected alternatives

### Inherit the active Frame or Layer Range

Those are editor-session facts and cannot be reconstructed reliably by an agent from
the request alone.

### Expose CLI Layer globs

Glob matching and ambiguous bare names are convenient shell syntax but are not
stable object addressing. Exact Layer addresses already cover the same compositions.

### Render Layers in Python or custom Lua compositing code

That would duplicate native stack order, Blend Mode, opacity, Background, Tilemap,
Reference, palette, and color-management semantics.

### Allow Frame Range or Tag in `export image`

Those inputs make output cardinality and animation behavior format-dependent and
belong to the explicit animation and sequence export Operations.
