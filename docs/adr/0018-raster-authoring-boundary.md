# ADR-0018: Separate Image structure from Paint intent in one raster module

- Status: Accepted
- Date: 2026-09-10

## Context

Aseprite already defines `Image` as its pixel-buffer object. SPA must preserve that
native language for inspecting and structurally transforming pixel data. Agents also
need higher-level authoring actions such as applying a rectangular pixel patch, drawing
a primitive, or filling a region. Treating all of those actions as generic Image setters
would obscure intent and make the CLI harder for agents to discover.

Creating independent Image and Paint subsystems would introduce the opposite problem.
Both surfaces operate on the same pixels, colors, masks, coordinate spaces, Cel/Image
selection, mutation unit, and Lua behavior. Separate modules would duplicate core
semantics and invite different answers for the same raster operation.

## Decision

Expose two public Command Groups owned by one Raster Authoring Domain Module:

- `image` follows Aseprite's native Image value. It owns Image observation,
  replacement, sizing, cropping, exact transforms, and other structural pixel-buffer
  operations.
- `paint` owns agent-facing raster authoring intent. It applies bounded bulk pixel
  patches, primitives, fills, and other proven drawing operations to a selected
  Cel/Image target.

The two Command Groups share one implementation authority for pixel formats, colors,
masks, coordinate spaces, target resolution, mutation behavior, and verification. They
do not define parallel pixel models or duplicate Lua handlers for equivalent behavior.
Their public color and pixel-color fields follow the discriminated Color Value and
explicit operation-specific conversion rules in ADR-0024. Packed Aseprite pixel
integers remain a private Kernel representation rather than a second public pixel
model.
Their Point and Rectangle fields follow ADR-0025. Raster writes use Image Pixel
coordinates, reject an out-of-bounds Rectangle by default, and report the actual
applied Rectangle when an Operation supports and the caller selects clipping.
When a raster Operation targets a Sprite Cel/Image, that Cel must already exist as
defined by ADR-0027. Paint does not inherit an editor preference that creates a Cel
implicitly; an agent can compose `cel add` and Paint in one Operation Plan.
When a raster Operation is constrained by a Selection, the request carries the
explicit Selection value defined by ADR-0029. The handler may materialize it through
Aseprite's native Selection API during execution but does not read hidden selection
state from a prior process or Plan Step.

The split is a public navigation and intent distinction, not a bounded-context split or
a requirement for separate packages. New raster capabilities are placed according to
their user-visible intent and can refine the catalog as vertical slices establish their
semantics.

## Consequences

- Public commands preserve Aseprite's native Image terminology.
- Agents can discover authoring actions without encoding every workflow as raw pixel
  replacement or per-pixel calls.
- One Domain Module prevents Image and Paint behavior from drifting.
- RGBA, Grayscale, and Indexed pixel operations preserve their distinct native
  meanings while sharing one public contract family.
- Raster bounds and clipping behavior are visible in the Operation contract and
  result rather than inherited from a helper implementation.
- Cel lifecycle remains explicit while a Plan keeps create-then-paint workflows in
  one Aseprite process and one Target Commit.
- Raster masks are explicit inputs, so absent, empty, and all-canvas Selection
  behavior cannot depend on editor state.
- The module must make shared-Image behavior through linked Cels explicit; the grouping
  decision alone does not decide whether an individual operation preserves, rejects, or
  detaches such sharing.
