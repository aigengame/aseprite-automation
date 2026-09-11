# spa command catalog

This document is the incremental, non-binding feature map for the `spa` command
surface. It shows the Aseprite capability territory that SPA intends to make
usable by agents and gives candidate command spellings so vertical slices have a
shared starting point.

The catalog is not a task tracker, a release promise, or a command registry:

- GitHub issues own commitments, prioritization, and delivery status.
- The installed `spa schema` Surface Manifest owns the callable Operations and
  schemas that a particular SPA installation actually provides.
- An entry here does not create an Operation Descriptor or imply that the command
  has shipped.
- Command names and group boundaries can change when an evidence-bearing vertical
  slice discovers better Aseprite-aligned semantics.

The catalog deliberately has no per-command status column. Such a column would
duplicate both the issue tracker and the installed Surface Manifest and would
inevitably drift from them.

## How the catalog grows

Commands are delivered as vertical slices rather than filled in horizontally by
group. An accepted slice establishes all of the following together:

1. the Aseprite-aligned term and user-observable behavior;
2. a typed public request, Operation Result, and Failure Codes;
3. an Operation Descriptor with Operation Determinism and projections into CLI help
   and the Surface Manifest;
4. one fixed Lua Operation Kernel handler used by standalone and Plan execution;
5. real-Aseprite end-to-end evidence, including independently reopened outputs for
   mutations and verified Artifacts for exports;
6. any refined semantic notes that future commands must preserve.

The catalog should be updated when a slice changes the shape or meaning of the
territory. Delivery state remains in the issue that owns the slice.

## Grouping and naming rules

- Use Aseprite's native object names where Aseprite already has a concept: `sprite`,
  `layer`, `frame`, `cel`, `tag`, `image`, `palette`, `selection`, `slice`,
  `tileset`, and `tilemap`.
- A Command Group is a public navigation aid, not necessarily a Domain Module.
  Closely related groups can share one module and behavior lifecycle.
- Keep inspection and validation beside the object they observe. Do not create
  generic top-level `inspection`, `analysis`, `quality`, or `validation` groups.
- Each inspection Operation defines a typed Inspection Scope and returns every fact
  promised for its normalized scope. Native absence uses a schema-defined null or
  empty collection; optional sections not requested are identified explicitly.
  Requested unsupported capabilities and exceeded Domain Bounds fail rather than
  yielding an unexplained partial result.
- Windowed or chunked inspection is domain-specific and reports its exact coverage
  and completeness. An Operation can use a Rectangle, Frame Range, page, chunk, or
  explicit Artifact projection without creating a global cursor or Observation
  Envelope.
- Use `create` and `delete` for standalone lifecycle, `add` and `remove` for
  membership in a containing object, `get` and `list` for reads, and `set` for an
  explicitly replaceable property. Prefer an Aseprite-native or domain-natural verb
  when those generic verbs obscure the behavior.
- Keep materially different Aseprite behaviors separate. For example, adding an
  empty Frame, duplicating a Frame, copying a Cel, and linking Cels are not aliases.
- Name public Frame ordinals `frame_number`. They are one-based, matching
  Aseprite's editor and Lua API; Frame Range endpoints are inclusive. Do not expose
  an ambiguous `index` field or leak a native CLI's zero-based frame offsets.
- Name persisted Frame timing `duration_ms` and use integer values from 1 through
  65535. Do not expose Lua floating-point seconds as a second public unit. A
  higher-level FPS input declares deterministic millisecond quantization and reports
  the resulting durations; export-format timing quantization remains an export fact.
- Represent public color and native pixel-color values with a discriminated Color
  Value: RGBA channels, Grayscale plus alpha, or a Palette Index. Do not expose
  packed pixel integers, conflate indexed transparency with alpha, or perform a
  cross-Color-Mode conversion without an explicit policy or Operation.
- Follow Aseprite's `x`, `y`, `width`, and `height` Rectangle shape. Rectangles cover
  half-open regions; width and height are non-negative. Each Operation declares its
  Coordinate Space and whether negative positions or empty Rectangles are meaningful.
  Raster writes reject out-of-bounds regions unless that Operation exposes an
  explicit clipping behavior and reports the Rectangle actually applied.
- Prefer bounded bulk authoring payloads over one process invocation per pixel or
  tile.
- Every mutating command declares a Target Sprite File or explicit In-place
  Mutation intent. Every read returns a domain-specific result. Every produced file
  is reported as an Artifact in the owning result.
- An ordinary Mutation resolves and validates its complete target set before
  changing it. The whole target set succeeds or no Target Commit occurs; skipped
  targets are not hidden in warnings and there is no generic best-effort flag.
- `validate` reports Validation Findings on successful execution. A failed
  invocation or unmet Plan Postcondition returns a Failure Envelope instead.
- Candidate names below are design inputs, not frozen compatibility promises.

## Meta commands

Meta commands describe SPA or its installed Aseprite runtime and do not belong to a
domain Command Group.

| Command | Intended meaning |
| --- | --- |
| `spa info` | Report the selected Aseprite executable, resource completeness, version, supported scripting capabilities, and evidence-backed Capability Gaps. |
| `spa version` | Report the installed SPA version. |
| `spa schema` | Emit the installed aggregate Surface Manifest. |
| `spa skill` | Emit or install the Agent Skill matched to the installed operation surface. |
| `spa <group> <command> --schema` | Emit one command's public input, result, and failure schemas plus invocation metadata. |

Ordinary parser help remains available as CLI behavior; it does not need a separate
Operation solely to appear in this catalog.

## Initial evidence-bearing territory

The first production tracer should exercise a coherent agent loop rather than a
large command count. The following spellings are candidates for that tracer and its
immediate follow-ups.

| Candidate command | Capability to prove |
| --- | --- |
| `spa sprite create` | Create a Sprite at an explicit Target Sprite File with dimensions, color mode, and initial frame/layer facts. |
| `spa sprite get` | Return the structural Sprite facts required to select later edits and verify persisted output. |
| `spa sprite validate` | Evaluate declared structural Sprite rules and return typed Validation Findings. |
| `spa layer add` | Add a typed Layer and return its native hierarchy and identity facts. |
| `spa frame add` | Add an empty Frame with explicit duration semantics. |
| `spa frame duplicate` | Duplicate the selected Frame without conflating duplication with empty-frame creation. |
| `spa cel copy` | Copy Cel content into an explicitly selected destination. |
| `spa cel link` | Establish Aseprite's linked-Cel relationship rather than copying pixels. |
| `spa tag add` | Add an animation Tag over an explicit Frame range and direction. |
| `spa paint apply` | Apply one canonical Pixel Patch to an explicitly addressed Cel/Image target. |
| `spa plan check` | Preflight an Operation Plan and report statically decidable problems without opening Aseprite. |
| `spa plan run` | Execute eligible read and mutation steps against one in-memory Sprite and commit at most one target. |
| `spa export image` | Export a still raster Artifact with verified format-specific facts. |
| `spa export sheet` | Export a sprite-sheet image and typed metadata Artifacts from explicit frame/tag selection. |
| `spa export gif` | Export an animated GIF Artifact and verify its persisted animation facts. |

This table is a product-slice hypothesis. The owning issues decide which commands
enter a delivery increment, and the installed Surface Manifest proves which of them
exist.

## Incremental domain territory

The following sections map broader Aseprite capability territory. They are expected
to gain, lose, or rename entries as real workflows establish precise semantics.

### `sprite`

Owns the Sprite lifecycle and Sprite-wide properties, not every operation on every
object contained by a Sprite.

| Candidate command | Intended meaning |
| --- | --- |
| `spa sprite create` | Create a new Sprite and commit it to an explicit target. |
| `spa sprite get` | Read complete Sprite-wide facts for an explicit Inspection Scope and identify sections not requested. |
| `spa sprite set` | Change explicitly supported simple Sprite-wide properties other than Color Mode. |
| `spa sprite change-color-mode` | Apply Aseprite Change Color Mode with source/target-specific Effective Palette, Grayscale, RGB Map Algorithm, Color Best Fit Criteria, and Dithering inputs. |
| `spa sprite assign-color-profile` | Apply Aseprite Assign Color Profile without changing stored pixels or Palette Entries. |
| `spa sprite convert-color-profile` | Apply Aseprite Convert Color Profile to applicable pixels and Palette Entries. |
| `spa sprite resize` | Resize the Sprite canvas using explicit scaling and anchoring semantics. |
| `spa sprite crop` | Crop the Sprite canvas to an explicit rectangle or supported content rule. |
| `spa sprite validate` | Check Sprite-wide structural rules. |

Color Profile is independent of Color Mode. Both Sprite operations use an explicit
target represented by Aseprite's `ColorSpace` API: `none`, `srgb`, or an exact ICC
file as applicable. Assign Color Profile changes interpretation without changing
stored pixels or Palette Entries. Convert Color Profile delegates Aseprite's native
pixel and Palette transformation before assigning the target. The commands are
explicit operations rather than fields of generic `sprite set`; they use normal
Mutation, Plan, Target Commit, and save/reopen semantics. The fixed Lua Kernel owns
`Sprite:assignColorSpace` and `Sprite:convertColorSpace` invocation and observations.
Python can preflight an ICC path and digest but cannot implement a color transform.
Results distinguish source, requested, and effective profile kind/name; ICC source
path/digest; changed Image and Palette facts; unchanged values for Assign; and native
runtime coverage, including Tileset behavior.

`sprite change-color-mode` and `export image.color_mode.change` use one accepted
Aseprite-aligned Change Color Mode request and the same fixed Lua Kernel behavior.
Target RGB accepts no conversion options. Target Grayscale requires
`to_gray: luma | hsv | hsl`. Target Indexed uses the Sprite's already established
Effective Palettes and requires RGB Map Algorithm and Color Best Fit Criteria; RGB
source additionally requires an explicit Dithering branch including `none`, while
Grayscale source rejects Dithering because the native path ignores it.
`rgb_map_algorithm` uses exact `default | rgb5a3 | octree` strings;
`color_best_fit_criteria` uses `default | rgb | linearizedRGB | ciexyz | cielab`.
Both fields are required. Explicit
`default` is valid, and Aseprite 1.3.18.5 resolves the RGB Map value to Octree. Missing,
unknown, numeric, case-variant, irrelevant, preference-derived, and fallback values
fail. Change Color Mode never generates or imports a Palette. Same-mode requests are
idempotent no-ops with no extra fields. Merge layers and Palette preparation stay
separate Plan-composable Operations. The Sprite command covers all applicable Cel and
Tileset Images and reports requested/effective mapping choices, exact Palette basis,
and Transparent Color Index effects; the export branch changes only its disposable
Sprite. RGB-to-Indexed requires one conditional `dithering` branch:

- `none` accepts no Matrix or Factor;
- `ordered` and `old` accept an optional Dithering Matrix addressed either by one
  exact installed matrix ID or by an explicit matrix file path; omission means
  Aseprite's native Bayer 8-by-8 default; and
- `error-diffusion` requires a finite `dithering_factor` in `0..1`, accepts no Matrix,
  and preserves Aseprite's native Floyd-Steinberg implementation.

The exact algorithm strings are `none | ordered | old | error-diffusion`. Grayscale-
to-Indexed rejects the entire branch because the native conversion ignores it. Unknown
or case-variant algorithms, numeric enums, inapplicable fields, ambiguous or missing
installed IDs, unreadable or invalid matrix files, and any resolution that would make
Aseprite silently fall back to Bayer 8-by-8 fail before conversion. Runtime-resource
discovery can occur in the Python adapter, but the fixed Lua Kernel owns matrix loading,
typed-to-native mapping, native invocation, and effective observations. Neither side
implements a Dithering algorithm. Results report requested/effective algorithm, Matrix
source/identity/resolution/dimensions when applicable, Factor when applicable, Palette
basis, and affected conversion facts.

### `layer`

Owns Aseprite Layer membership, hierarchy, properties, and layer-specific behavior.
Tilemap Layers remain native Layers but can share implementation with the tile
authoring module. A new SPA-created Sprite enables Aseprite's native
`useLayerUuids` option by default unless creation explicitly disables it. Existing
Sprites preserve their current setting. A `layer_uuid` is a persistent
cross-Operation address only when that option is enabled; a process-generated UUID
from a Sprite that does not persist Layer UUIDs is not advertised as one. Layer
Operations can instead use a `layer_stack_path`: the sequence of one-based native
`Layer.stackIndex` values from the Sprite root to the target. It addresses the
current hierarchy exactly, including duplicate names, but is not a Persistent
Identity. A convenient `layer_name` succeeds only when exactly one Layer in the
Operation's documented scope matches it. Inspection returns current hierarchy,
name, stack path, and the persisted UUID when available; reorder and reparent
results return the resulting stack path.

`layer add` declares `kind` explicitly. For `kind: tilemap`, the request must also
declare one Tilemap Layer Tileset Intent: `tileset.create` supplies the new Tileset's
name, Grid, and Base Index, while `tileset.share` exactly addresses one existing
Tileset. Although this remains the public Layer lifecycle Operation, the tilemap
variant is implemented by the tile-authoring Domain Module.

| Candidate command | Intended meaning |
| --- | --- |
| `spa layer list` | List Layers with native hierarchy, names, stack paths, and persisted UUIDs when available. |
| `spa layer get` | Read one Layer's type, hierarchy, current address facts, and editable properties. |
| `spa layer add` | Add a declared native Layer kind; the tilemap variant requires explicit create-or-share Tileset intent and returns both Layer and Tileset facts. |
| `spa layer remove` | Remove Layers under the Operation's explicit target-count rule. |
| `spa layer set` | Set supported Layer properties. |
| `spa layer set-tileset` | Rebind one Tilemap Layer to an exactly addressed Tileset through explicit Tile mapping and Grid policies. |
| `spa layer move` | Reorder or reparent selected Layers. |
| `spa layer merge` | Apply an explicitly defined native merge behavior. |
| `spa layer convert-to-background` | Convert one supported Image Layer into the Sprite's Background Layer using an explicit Background Color and report all Cel normalization. |
| `spa layer convert-from-background` | Convert the Background Layer into a regular transparent Image Layer while reporting the resulting Layer and Cel facts. |

### `frame`

Owns Frame membership, ordering, duration, and whole-frame duplication. Public
requests and results use one-based `frame_number` values. Every Frame Range is
inclusive at both endpoints. `frame add` inserts an empty Frame at an explicit
position with an explicit duration; transparent Layer intersections remain absent,
while an existing Background Layer receives its required Cel from an explicit
Background Color. `frame duplicate` defaults to insertion immediately after its
source and requires `cel_mode: copy | link`; it copies the source duration unless
overridden and does not consult `Layer.isContinuous`. Native Tag Range adjustments
and resulting Frame Numbers are returned. All Frame timing requests and results use
integer `duration_ms` in the persisted Aseprite range from 1 through 65535.

| Candidate command | Intended meaning |
| --- | --- |
| `spa frame list` | List Frames and integer `duration_ms` values. |
| `spa frame get` | Read one Frame and its animation-relevant facts using persisted millisecond timing. |
| `spa frame add` | Add an explicitly timed empty Frame at a one-based insertion position, with Background Color when required. |
| `spa frame remove` | Remove selected Frames. |
| `spa frame set` | Set `duration_ms` or another supported Frame property. |
| `spa frame duplicate` | Duplicate one whole source Frame using an explicit `copy` or `link` Cel mode and copied-or-overridden duration. |

### `cel`

Owns the Layer-by-Frame Cel relationship, placement, opacity, image assignment,
copying, and linking. `cel link` establishes Aseprite's native shared Cel data;
`cel unlink` explicitly copies that data and Image to make the selected Cel
independent. Cel absence is distinct from a Cel with transparent or otherwise empty
Image content. `cel add` requires an unoccupied Layer/Frame intersection and fails
instead of inheriting `Sprite:newCel()` replacement behavior. Raster operations
require an existing Cel/Image and never create one implicitly. An agent composes
`cel add` and Paint inside one Plan when it intends both changes. Raster operations
never unlink implicitly.

A Background Layer follows Aseprite's distinct lifecycle: a Sprite has at most one,
and it contains a full-canvas opaque Cel for every Frame. `cel remove` rejects a
Background Cel because it cannot become absent. `cel clear` preserves the Cel and
fills it with the request's Background Color; on a transparent Layer it preserves the
Cel and clears to transparent pixels. Conversion to Background declares that color
and reports created Cels, canvas expansion, position normalization, and opacity
normalization rather than inheriting hidden editor color state.

| Candidate command | Intended meaning |
| --- | --- |
| `spa cel list` | List Cels over bounded Layer and Frame selections. |
| `spa cel get` | Read one Cel's placement, opacity, link, and Image facts. |
| `spa cel add` | Add a Cel to an empty Layer/Frame intersection. |
| `spa cel remove` | Remove selected Cels from Layer kinds where the intersection can become absent; reject Background Cels. |
| `spa cel clear` | Preserve selected Cels while clearing to transparency or an explicit Background Color according to Layer kind. |
| `spa cel set` | Set supported Cel properties. |
| `spa cel copy` | Copy Cel content into an explicit destination. |
| `spa cel link` | Link destination Cels to a source Cel's native shared Image. |
| `spa cel unlink` | Replace a linked Cel with independent Image content. |

### `tag`

Owns Aseprite Tag ranges, names, colors, repeat counts, and animation directions.
Tag range endpoints are inclusive Frame Numbers. `animation_direction` uses
`forward`, `reverse`, `ping-pong`, or `ping-pong-reverse`. Native `repeats` is an
integer from 0 through 65535, where zero means unspecified rather than universally
infinite. `tag add` receives range, direction, and repeats explicitly. A consuming
Playback or Export Operation declares whether it applies Aseprite Tag semantics or
a caller-specified play count and reports its actual expanded Frame Number sequence.
Tag read and mutation requests address one Tag with exactly one operation-specific
field: current one-based `tag_index`, or `tag_name` when it matches exactly one Tag.
Names remain Aseprite-compatible and may be duplicated; ambiguous names fail rather
than selecting the first match. A Tag Index follows the current `Sprite.tags` order
and can change after a range edit, add, or removal. Results return the complete Tag
facts and current index. SPA does not expose Aseprite's process-local object ID or
persist a synthetic Tag identity.

| Candidate command | Intended meaning |
| --- | --- |
| `spa tag list` | List Tags with current `tag_index`, inclusive Frame Range, Animation Direction, and raw persisted `repeats`. |
| `spa tag get` | Read one Tag by `tag_index` or unique `tag_name` without rewriting zero repeats as infinite. |
| `spa tag add` | Add a Tag with explicit Frame Range, `animation_direction`, and `repeats`, returning its resulting current index. |
| `spa tag remove` | Remove one Tag addressed by `tag_index` or unique `tag_name`. |
| `spa tag set` | Set one addressed Tag's supported properties and return its complete resulting facts and current index. |

### `image` and `paint` (ADR-0018)

`image` follows Aseprite's native Image value and its observation and structural
pixel-buffer operations. `paint` exposes agent-facing authoring actions applied to
a selected Cel/Image target. Both are public Command Groups owned by one Raster
Authoring Domain Module, with shared pixel, color, mask, coordinate, and mutation
semantics rather than parallel implementations. A raster mutation preserves native
linked-Cel sharing: selected Cels are reduced to unique shared Images so an Image is
mutated once, and the Operation Result reports every Cel affected through that
sharing. An agent that needs an isolated edit composes `cel unlink` before the raster
Operation in the same Plan. Image pixel payloads and Paint colors use the target
Sprite's Color Mode. An Indexed pixel uses its native Palette Index against the
Palette applicable to its Frame; any resolved RGBA is a separate observation rather
than a replacement value. Cross-Color-Mode authoring requires an explicit conversion
policy or conversion Operation.

Image and Paint regions use zero-based Image Pixel coordinates and half-open
Rectangles. A raster write requires an existing Cel/Image and does not silently
create a Cel or clip at Image bounds.

Pixel Region Snapshot is the complete canonical Published Language for bounded
Raster pixels. It contains one positive half-open Rectangle in Image Pixel space, an
Aseprite `color_mode`, and exactly `height` ordered rows. Each row is a sequence of
positive-length runs whose lengths total `width`; each run carries one Color Value
compatible with the Color Mode, and adjacent equal runs must be merged. Row order and
run lengths imply relative coordinates inside the Rectangle. No pixel can be omitted
and there is no transparent or other default. RGB uses `rgba`, Grayscale uses
`grayscale`, and Indexed preserves `palette-index` rather than expanding stored values
to RGBA. Inline JSON and JSON Artifact projections use the same schema. When the
inline Domain Bound is exceeded, the complete value moves to an Artifact rather than
being truncated or re-encoded. Descriptor schemas validate transport shape; the
fixed Lua Kernel owns semantic coverage, value compatibility, canonicalization, Image
reading, and Image writing.

`image get` requires one positive Rectangle fully contained in an existing
non-Tilemap Cel Image. It returns that exact complete Snapshot without clipping and
reports Color Mode, mask/transparent value, Layer kind, native Image sharing and
associated Cels, and the target Frame's Effective Palette and range for Indexed
content. Existing ordinary Image, Background, and Reference Cels are readable.

`image replace` accepts an inline Snapshot or JSON Artifact whose Rectangle is
exactly `(0,0,width,height)` for the current Image and whose Color Mode matches it.
It replaces stored pixels without changing dimensions, Cel positions, Background
invariants, Reference floating-point bounds, or Color Mode. Geometry changes use
`image resize`, `image crop`, or `image canvas-resize`; Color Mode changes use the
explicit Change Color Mode operation. A linked Image is replaced once and all sharing
Cels remain linked. Ordinary Image, Background, and Reference Cels are supported;
Tilemap, absent, and non-Cel targets fail. Selection state is not applied. Snapshot
validation and pixel replacement form one all-or-nothing Mutation. Results report
input form, complete affected Cel/link and unchanged geometry facts, Pixel Format,
and before/after content digest, verified after save/close/reopen.

Pixel Patch is the canonical sparse Raster mutation value. It declares one positive
half-open Rectangle and `color_mode`, then lists zero or more runs with absolute
Image Pixel `x/y`, positive `length`, and one compatible Color Value. Runs are ordered
by `y` then `x`, contained by the declared Rectangle, non-overlapping, and merged when
adjacent values are equal. Listed pixels receive the exact stored values; omitted
pixels remain unchanged. An empty run list is an explicit no-op. Inline JSON and JSON
Artifact inputs use the same schema. Descriptor schemas validate transport shape;
the fixed Lua Kernel owns semantic normalization, clipping, Selection intersection,
Palette applicability, and writes.

`paint apply` writes one Pixel Patch to an existing ordinary Image or Background Cel.
Its `clipping` defaults to `reject`, requiring the declared Rectangle to be contained
by Image bounds. Explicit `clip` intersects runs with Image bounds and reports every
skipped segment; a resulting empty write set is a valid no-op. An optional explicit
Selection Application further intersects writes after mapping each target Image Pixel
to Canvas Pixel through the addressed Cel position. Omitted Selection means no
restriction and an explicit Empty Selection produces a reported no-op. Current editor
Selection state is ignored. Selection mapping is based on the addressed Cel even
though native sharing can make the resulting Image change visible through other Cels.

The patch Color Mode must match the target. Indexed Palette Indexes must exist in the
Effective Palette of every Frame whose Cel shares the Image; native rendering may
still differ between Palette Changes and is reported. Background writes must satisfy
the native opaque Background postcondition for the target Color Mode. Reference Cels
fail because their floating-point bounds need a separate pixel-to-Canvas mapping;
Tilemap, absent, and non-Cel targets also fail. A linked Image is mutated once and all
sharing Cels remain linked. Patch validation and every write are one all-or-nothing
Mutation. Results include input form, requested/applied Rectangle and runs, pixels
written or skipped by bounds and Selection, Palette facts, all affected Cels/links,
unchanged geometry, and before/after content digest, verified after save/close/reopen.

`paint apply` performs stored-value replacement, not alpha/opacity/BlendMode
composition or cross-Color-Mode conversion. Those semantics belong to the separate
candidate `paint composite`, which will use Aseprite compositing vocabulary without
changing Pixel Patch meaning. Python transports the request but cannot implement or
assemble another patch algorithm.

`paint composite` accepts a Pixel Region Snapshot inline or through the identical
JSON Artifact form. The Kernel constructs a source Image by rebasing the Snapshot
Rectangle to `(0,0)` and places that origin at the request's integer `position` in
target Image Pixel space. The request requires integer `opacity` in `0..255`; values
outside the range fail instead of inheriting Aseprite's clamp. It also requires one
supported Aseprite BlendMode: `normal`, `multiply`, `screen`, `overlay`, `darken`,
`lighten`, `color-dodge`, `color-burn`, `hard-light`, `soft-light`, `difference`,
`exclusion`, `hue`, `saturation`, `color`, `luminosity`, `addition`, `subtract`, or
`divide`. Script enum values that native `Image:drawImage` silently maps to Normal are
not accepted under another name.

Source and destination Color Modes must match. Cross-mode composition begins with an
explicit Change Color Mode or operation-specific conversion rather than implicit
coercion. The clipping and optional
Selection Application contracts are identical to `paint apply`: default `reject`,
explicit `clip`, addressed-Cel Image-to-Canvas mapping, no current Selection, and
complete applied/skipped facts. The Kernel produces native composite results, then
commits changes at the selected pixels so Selection does not become editor state.
Ordinary Image and Background Cels are supported, with the native opaque Background
postcondition. Reference, Tilemap, absent, and non-Cel targets fail. A linked Image is
composited once and sharing remains intact.

RGB and Grayscale execution delegates to native `Image:drawImage` through the fixed
Lua Kernel handler. Indexed composition additionally requires
`palette_frame_number`, which must select the addressed target Cel Frame's Effective
Palette. Aseprite 1.3.18.5's Cel-associated `Image:drawImage` uses Palette 0, so Indexed
delivery is gated by a real-runtime slice proving a Palette-correct native delegation
route, such as isolated temporary Sprite state or temporary Palette substitution with
complete restoration and rollback. Until then `spa info` reports the Color-Mode-
specific Capability Gap and the command returns a typed refusal. It never falls back
to Palette 0 or a rewritten Lua/Python BlendMode implementation. Indexed composition
remains part of the intended command contract.

Validation, native composition, Selection application, Background postcondition, and
pixel commit are one all-or-nothing Mutation. Results return source and target
Rectangles, applied/clipped/selected coverage, opacity, BlendMode, optional Composite
Palette Basis, changed/skipped pixel counts, all affected Cels/links, unchanged
geometry, and before/after content digest, verified after save/close/reopen.

Native Tool Invocation is the private fixed-Lua-Kernel mechanism for Paint primitives
that correspond to Aseprite editor tools. Each public `paint line`, `paint rectangle`,
`paint ellipse`, or `paint fill` descriptor fixes its native tool and exposes a typed
operation-specific request; SPA does not publish a generic `use-tool` escape hatch.
The Kernel supplies the addressed Cel, Layer, and Frame plus every result-affecting
option owned by the Operation, including applicable Color Values, Brush, Ink,
opacity, tolerance, contiguous mode, Selection mode, Tilemap mode, and Tileset mode.
No active tool, foreground/background color, active Brush, active site, or mutable
tool preference may choose public behavior.

Public primitive geometry uses Image Pixel space. The Kernel translates it through
the addressed Cel position to the Canvas coordinates consumed by `app.useTool`.
Paint's default bounds refusal, explicit clipping, and explicit Selection Application
remain authoritative. Native execution must not implicitly create a Cel, expand the
Image, move the Cel, or break links; an agent composes `cel add` or
`image canvas-resize` when those changes are intended. The Kernel validates the
observed changed region before Target Commit. It supports ordinary Image and
Background Cels subject to the opaque Background postcondition; Reference, Tilemap,
absent, and non-Cel targets use other domain operations or fail.

Any editor/tool state changed to invoke the native tool is captured and restored for
success and failure within that invocation. This is functional isolation required to
make the requested Paint behavior explicit, not a persistent session, lock,
concurrency, or generalized state-management subsystem. Linked Image semantics and
complete affected-Cel reporting remain unchanged.

`Image.context`/`GraphicsContext` may support internal diagnostics or non-authoritative
preview experiments but cannot replace a public editor-tool semantic. A primitive is
delivered after a real `aseprite --script` slice proves non-interactive execution,
complete control of configurable result-affecting state, preference perturbation
independence, standalone/Plan atomicity, state restoration, Linked Image behavior,
and its declared Operation Determinism. Deterministic primitives require exact native
pixel parity. Native-stochastic primitives require proof of native delegation,
declared output bounds and invariants, and complete actual-result observation rather
than identical replayed pixels. A failed proof yields that primitive's typed
Capability Gap; SPA does not silently switch renderer or implement it in Python.

Standard Paint Brush is the shared typed value for Aseprite's `circle`, `square`, and
`line` Brush footprints. `size` is a positive integer and invalid values fail instead
of being clamped to 1. Circle has fixed angle 0 and rejects an angle field. Square and
Line require an integer `angle` from `-180` through `180`. A Line Brush is an oriented
footprint stamped by a tool; it is not the Line tool itself. Image Brush is a distinct
Aseprite Brush kind with mask, center, pattern, pattern-origin, and color-replacement
semantics and receives its own contract rather than an implicit standard variant.

`paint line` fixes Native Tool Invocation to Aseprite's Line tool and supplies exactly
two Image Pixel Points, `from` and `to`. Equal Points produce a native single-point
stroke. The request also requires a Standard Paint Brush, one compatible Color Value,
integer `opacity` in `0..255`, and one supported Aseprite Ink: `simple`,
`alpha-compositing`, `copy-color`, or `lock-alpha`. The Kernel explicitly supplies the
left button, target Cel/Layer/Frame, Brush, color, Ink, opacity, and safe fixed values
for other invocation options; no active state supplies them. Invalid opacity fails
rather than inheriting native clamping.

Shading Ink remains part of the Paint capability, but `app.useTool` does not accept
the complete Shade configuration. Until a dedicated real-runtime slice proves that
configuration can be supplied and restored explicitly, a Shading Line request is a
typed Capability Gap and never reads editor Shade preferences. Image Brush follows
the same delivery rule under its separate contract.

Default bounds refusal, explicit clipping, and explicit Selection Application reuse
the Paint contracts and operate on the native rendered Brush footprint, not just the
endpoint Rectangle. Native execution cannot create a Cel, expand its Image, move the
Cel, or break Image links. Ordinary Image and Background Cels are supported subject
to the opaque Background postcondition; Reference, Tilemap, absent, and non-Cel
targets fail. A linked Image is painted once and results enumerate every affected
Cel. The all-or-nothing result includes endpoints, normalized Brush, Ink, opacity,
requested and actual affected regions, pixels clipped or excluded by Selection,
changed pixel count, associated Cels/links, and before/after content digest, verified
after save/close/reopen.

`paint rectangle` and `paint ellipse` share the Paint Shape request. It requires a
positive half-open `bounds` Rectangle in Image Pixel space and a `style` of `outline`
or `filled`, plus Standard Paint Brush, compatible Color Value, integer opacity, one
accepted Ink, clipping, and optional explicit Selection Application. The Kernel maps
the Rectangle to the native tools' inclusive Points `(x,y)` and
`(x+width-1,y+height-1)`.

Native Tool Invocation maps Rectangle outline/filled to `rectangle`/
`filled_rectangle` and Ellipse outline/filled to `ellipse`/`filled_ellipse`.
Invocation explicitly controls and restores any optional-fill preference read by the
outline tools, so requested style cannot drift with editor state. One-pixel width or
height retains the selected native shape's degenerate behavior and is not rewritten
as Paint Line. Outline and filled tools retain their native Standard Brush footprint;
the actual changed region, bounds refusal, and explicit clipping are evaluated from
that footprint rather than the geometric Rectangle alone.

No Shift-like proportion constraint, from-center behavior, rotation modifier, or
keyboard state is implicit. Those future geometric intents require typed fields and
native validation before becoming part of the request. Native execution cannot
create a Cel, expand its Image, move it, or break links. Ordinary Image and Background
Cels are supported subject to the opaque Background postcondition; Reference,
Tilemap, absent, and non-Cel targets fail. Results return shape kind, style, requested
bounds, normalized Brush/Ink/opacity, native endpoint mapping, actual affected region,
pixels clipped or excluded by Selection, changed count, every affected Cel/link, and
before/after content digest, verified after save/close/reopen.

Rectangle and Ellipse have independent real `aseprite --script` editor-parity gates.
A failed proof produces the affected shape's Capability Gap without changing the
other shape or switching to GraphicsContext or Python geometry.

`paint fill` fixes Native Tool Invocation to Aseprite's `paint_bucket` tool. Its
request requires one Image Pixel `seed`, a compatible Color Value, integer `opacity`
and `tolerance` in `0..255`, an accepted Ink, explicit `contiguous`, Aseprite Refer To
as `active-layer` or `all-layers`, and explicit `stop_at_grid`. A contiguous request
also requires Pixel Connectivity as `four-connected` or `eight-connected`; a
non-contiguous request forbids connectivity rather than accepting an ignored field.
Paint Fill does not accept a Brush.

`active-layer` refers to the explicitly addressed target Layer, not mutable editor
state. `all-layers` asks native Aseprite to render the visible Layers for the
addressed Frame as the color-matching source while applying the fill only to the
target Cel. Non-contiguous mode changes every matching source position within the
effective fill bounds. Tolerance retains Aseprite's native per-Color-Mode comparison
semantics; SPA does not reinterpret it as perceptual color distance.

`stop_at_grid: false` maps to native `NEVER`; `true` maps to native `ALWAYS` and uses
the Sprite's persisted Grid to restrict the effective fill bounds to the seed's Grid
cell. SPA does not use `IF_VISIBLE`, because GUI grid visibility is not part of the
request and the explicit boolean selects both possible results directly. The Kernel
sets and restores Refer To, Stop at Grid, and Pixel Connectivity preferences around
the invocation because `app.useTool` accepts tolerance and contiguous directly but
not those three Paint Bucket settings.

Existing clipping, explicit Selection Application, no-implicit-Cel-or-Image-change,
Background, Linked Image, transaction, and postcondition rules apply. Results return
the seed, normalized Paint inputs, Refer To and effective source scope, contiguous
mode and applicable connectivity, Stop at Grid and exact effective Grid cell, the
requested and actual affected regions, pixels clipped or excluded by Selection,
changed count, every affected Cel/link, and before/after content digest. A real
headless editor-parity gate must prove native output and preference restoration;
failure yields Paint Fill's typed Capability Gap without a Lua/Python flood-fill
fallback.

`paint pencil` fixes Native Tool Invocation to Aseprite's `pencil` tool. It accepts
one non-empty ordered Image Pixel `points` sequence and sends it as one native
press/move/release gesture. A one-Point sequence is a valid point mark. SPA preserves
the exact request order and multiplicity: it does not deduplicate, simplify,
resample, interpolate, close, or otherwise normalize the path before invocation.

The request also requires a Standard Paint Brush, compatible Color Value, integer
`opacity` in `0..255`, an accepted Ink, and one Aseprite Freehand Algorithm:
`regular`, `pixel-perfect`, or `dots`. Regular uses native line-intertwining between
successive samples, Pixel-perfect uses Aseprite's pixel-perfect intertwiner, and Dots
stamps only through the native no-intertwiner path. The native algorithm remains the
authority for the pixels between or at supplied Points; the request is not a promise
that every Point becomes a changed pixel.

Existing native Brush-footprint bounds, explicit clipping and Selection Application,
no-implicit-Cel-or-Image-change, Background, Linked Image, transaction, and
postcondition rules apply. Pencil does not absorb the Line, Spray, or Eraser tools.
Image Brush and Shading Ink retain their separate intended-capability gates.

Aseprite 1.3.18.5's script path constructs Pointer samples without configurable
pressure, velocity, tilt, or GUI Paint Dynamics, and its source explicitly notes the
headless Dynamics limitation. Paint Dynamics therefore remain an intended functional
Capability Gap. SPA cannot inherit GUI Dynamics or simulate them with Python or a
second Lua renderer.

Regular, Pixel-perfect, and Dots have independent real `aseprite --script`
editor-parity gates. Dots requires special proof because the exact-version source
contains it while the public `app.useTool` documentation lists only algorithm values
0 and 1. A failed algorithm reports its typed Capability Gap without hiding proven
algorithms. Results return the exact input Points, algorithm, normalized Brush/Ink/
opacity, requested and actual native coverage, clipping/Selection counts, every
affected Cel/link, and before/after content digest, verified after save/close/reopen.

`paint eraser` fixes Native Tool Invocation to Aseprite's `eraser` tool. It reuses
Paint Pencil's non-empty ordered Image Pixel `points`, single press/move/release
gesture, Standard Paint Brush, integer `opacity` in `0..255`, and explicit `regular`,
`pixel-perfect`, or `dots` Freehand Algorithm. Point preservation, native
intertwining, actual Brush-footprint bounds, clipping, Selection, Linked Image,
transaction, and postcondition rules are identical. It does not accept a generic Ink
or public mouse button.

The required Eraser behavior is a discriminated value:

- `erase` selects Aseprite's native left-button Eraser Ink. On a transparent Layer it
  accepts no color and uses native alpha erasure for RGB/Grayscale or the Sprite's
  Transparent Color Index for Indexed content. On a Background Layer it requires one
  compatible `background_color`; the fixed Lua Kernel sets and restores Aseprite's
  background-color preference because this native path does not consume
  `app.useTool.bgColor`.
- `replace-foreground-with-background` selects the native right-button
  `replace_fg_with_bg` Ink and requires compatible `foreground_color` and
  `background_color`. It replaces matching foreground values only where the native
  Brush gesture applies.

Fields belonging to the other behavior are rejected rather than ignored. Image Brush
and Paint Dynamics retain their functional Capability Gaps. Every behavior,
Freehand Algorithm, Color Mode, transparent Layer, and Background Layer combination
has an independent real `aseprite --script` editor-parity gate. Failure returns the
specific typed Capability Gap and never falls back to Pencil with alpha zero, Python,
or another Lua eraser. Results return exact Points, behavior, normalized Brush/
opacity/algorithm and applicable colors, requested and actual coverage, clipping and
Selection counts, every affected Cel/link, native transparency or replacement facts,
and before/after content digest, verified after save/close/reopen.

Operation Determinism is required Operation Descriptor metadata and is projected in
the Surface Manifest and each Operation Result. `deterministic` means the same
validated request, source state, supported runtime, and declared environment facts
produce the same governed domain result. It does not promise byte-identical files
unless the owning Operation makes that stronger guarantee. `native-stochastic` means
Aseprite intentionally uses native randomness that SPA cannot seed. Such an Operation
still has explicit controllable inputs, atomic execution, and verified actual output,
but exact pixel replay is not promised.

`paint spray` is intended to fix Native Tool Invocation to Aseprite's `spray` tool.
It accepts one non-empty ordered Image Pixel `points` gesture, Standard Paint Brush,
compatible Color Value, integer `opacity` in `0..255`, an accepted Ink, Spray Width
in Aseprite's `1..32` range, and Spray Speed in `1..100`. Spray uses its native
overlap trace and random Brush placement; it rejects Freehand Algorithm because that
setting does not govern the native Spray trace. Existing actual-coverage bounds,
clipping, Selection, target, Linked Image, transaction, and postcondition rules apply.

Paint Spray declares `native-stochastic`. Aseprite 1.3.18.5 seeds its C random source
from process time and exposes no Spray seed, so SPA reports actual affected region,
changed count, content digest, and persisted pixels without promising exact replay.
SPA does not add a random seed or implement its own distribution.

The same runtime also resets a Tool's preferences on its first headless
`app.useTool` invocation, while `app.useTool` has no Spray Width or Speed arguments.
The exact source indicates that the reset happens only once per Tool per process. A
delivery slice must therefore test a fixed-Lua-Kernel route that primes native Spray
on an isolated temporary Sprite, sets the requested native width/speed preferences,
invokes the real target, and restores state. Until that route proves native behavior,
no persistent temporary document, and all-or-nothing failure handling, `paint spray`
is absent from the Surface Manifest and `spa info` reports a version-specific
Capability Gap. SPA does not ship a fixed-default-only partial command.

`paint gradient` is intended to fix Native Tool Invocation to Aseprite's `gradient`
tool and declares `deterministic` Operation Determinism. It requires exactly two
ordered Image Pixel Points, `from` and `to`, whose order defines the foreground-to-
background direction. `from` is also the native Flood Fill seed. Equal Points retain
the native Gradient tool's result and are not rewritten as Fill or a solid-color
operation.

The request requires compatible `foreground_color` and `background_color`, integer
`opacity` in `0..255`, Gradient Type `linear` or `radial`, and a Dithering Matrix
choice of `none` or one uniquely resolved installed Aseprite matrix name. Missing or
ambiguous named matrices fail; no request silently falls back to no dithering. The
result reports the resolved matrix identity and available matrix facts. Dithering
Matrix is distinct from export/color-conversion Dithering Algorithm and from Paint
Dynamics.

Gradient reuses Paint Fill's native matching controls: tolerance, contiguous mode,
required Pixel Connectivity when contiguous, Refer To `active-layer` or `all-layers`,
and Stop at Grid. It also reuses clipping, explicit Selection Application, target,
Background, Linked Image, transaction, and postcondition rules. Indexed execution
uses and reports the addressed target Frame's Effective Palette. Paint Gradient
accepts no Brush, generic Ink, Freehand Algorithm, or random seed; its tool fixes
native Gradient Ink.

In Aseprite 1.3.18.5, the native Tool Loop obtains Gradient Type and Dithering Matrix
from the GUI Context Bar, marks headless support as TODO, and `app.useTool` exposes no
corresponding arguments. Unlike Tool Preferences, this state has no source-evident
headless priming route. A real negative probe must confirm the runtime behavior.
Until a supported explicit route passes exact editor-pixel parity, option-independence,
state restoration, atomicity, and persistence gates, `paint gradient` is absent from
the Surface Manifest and `spa info` reports a version-specific Capability Gap. SPA
does not substitute Paint Composite, GraphicsContext, Python, or a custom Lua
gradient renderer.

Aseprite's Curve, Polygon, and Contour tools retain three separate Operations. They
reuse established Point, Standard Paint Brush, Color Value, opacity, Ink, bounds,
clipping, Selection, target, relationship, transaction, and result components where
applicable, but SPA introduces no universal Path, Segment, or Vector Shape model.

`paint curve` is the intended projection of native `curve`, Four Points Controller,
and Bézier Intertwiner. Its ordered roles are start, first control Point, second
control Point, and end; they are not an arbitrary segment list. It declares
`deterministic` Operation Determinism and requires Standard Paint Brush, compatible
Color Value, integer `opacity` in `0..255`, and accepted Ink. Curve is an unfilled
native Brush trace and accepts no fill, closure, Freehand Algorithm, or generic Path
fields. `paint polygon` is the intended projection of native `polygon` and its
Point-by-Point Controller; its ordered vertices use native always-filled closure.
`paint contour` projects native `contour`:
one ordered freehand gesture is closed and filled by the tool rather than interpreted
as a Polygon click sequence or an outlined path.

In Aseprite 1.3.18.5, scripted `app.useTool` performs one press, zero or more
movements, and one release. The Curve controller expects four interaction phases and
the Polygon controller expects repeated clicks followed by completion. Each therefore
needs a real headless negative or positive probe before publishing a descriptor.
Contour uses a Freehand Controller that the script gesture can express and receives
its own positive delivery slice. Failure of any probe produces only that Operation's
version-specific Capability Gap.

A real Aseprite 1.3.18.5 negative probe supplied two four-Point requests with identical
start/end roles and materially different control roles. Both `app.useTool` calls
returned normally, both produced zero opaque pixels, and the control change was not
observable. The process result is therefore not semantic success: this scripting path
cannot complete the Four Points Controller. On that runtime, `paint curve` is absent
from the Surface Manifest and `spa info` reports a typed Controller Capability Gap
with runtime, tool, controller, and probe evidence.

Paint Curve can enter a future runtime's Surface Manifest when a supported native
script route completes the controller, makes all four roles independently observable,
and passes exact editor parity, target, Brush, Color Mode, Ink, opacity, bounds,
clipping, Selection, Background, Linked Image, atomicity, persistence, and structured
postcondition gates. SPA does not expose a zero-effect command, ignore control Points,
degrade Curve to Line, drive GUI mouse interaction, call GraphicsContext, or implement
Bézier evaluation/rasterization in Lua or Python.

`paint polygon` declares `deterministic` Operation Determinism. Its intended request
contains an ordered Image Pixel `vertices` sequence, Standard Paint Brush, compatible
Color Value, integer `opacity` in `0..255`, and accepted Ink. The Point-by-Point
Controller remains authoritative for vertex accumulation and completion, and the
native tool remains authoritative for closure, filling, Brush coverage, and
degenerate input behavior. The request accepts no open/outline switch, explicit
closing Point, Freehand Algorithm, mouse-event stream, or generic Path fields.

A real Aseprite 1.3.18.5 negative probe supplied different intermediate vertices
while preserving the first and last vertices. Both `app.useTool` calls returned
normally, both produced zero opaque pixels, and the intermediate vertices were not
observable. A second negative case repeated the first vertex at the end in an attempt
to force completion; instead of the intended Polygon it filled all 400 pixels of the
20-by-20 probe canvas. Synthetic closure is therefore unsafe and is not a request
protocol.

On that runtime, `paint polygon` is absent from the Surface Manifest and `spa info`
reports a typed Controller Capability Gap with runtime, tool, controller, and probe
evidence. A runtime can publish it when a supported native scripting route makes each
vertex and Point-by-Point completion observable and passes exact editor parity,
target, Brush, Color Mode, Ink, opacity, bounds, clipping, Selection, Background,
Linked Image, atomicity, persistence, and structured postcondition gates. The
delivery slice must derive accepted vertex cardinalities and degenerate cases from
native editor evidence rather than inventing geometry restrictions.

SPA does not repeat the first vertex as a completion sentinel, chain independent
`app.useTool` calls, alias Polygon to Contour, drive GUI mouse interaction, call
GraphicsContext, or implement polygon filling in Lua or Python.

`paint contour` declares `deterministic` Operation Determinism and fixes Native Tool
Invocation to Aseprite's `contour` tool. It accepts one non-empty ordered Image Pixel
`points` sequence and preserves its order and multiplicity as one press/move/release
Freehand gesture. A one-Point sequence remains valid native input. SPA does not
deduplicate, simplify, interpolate, pre-close, or reinterpret the sequence as Polygon
vertices.

The request requires Standard Paint Brush, compatible Color Value, integer `opacity`
in `0..255`, an accepted Ink, and the operation-specific Freehand Algorithm `regular`
or `pixel-perfect`. Regular uses Aseprite's line intertwiner before final native
polygon filling; Pixel-perfect uses Aseprite's pixel-perfect processed stroke as the
fill boundary. Closure and filling are fixed Contour behavior, so the request accepts
no `closed`, `filled`, `outline`, or generic Path fields. It also accepts no public
mouse button.

Aseprite 1.3.18.5's editor exposes Regular and Pixel-perfect for Contour, and its
public `app.useTool` contract documents algorithm values 0 and 1. SPA therefore does
not expose the source-internal `dots` value for this Operation. The same scripting
path cannot provide pressure, velocity, tilt, or GUI Paint Dynamics, so those remain
a distinct functional Capability Gap rather than simulated inputs.

A direct real-runtime discovery probe confirmed that both documented algorithms run
headlessly through native Contour and produce distinct filled raster results. That
probe supports the contract but does not replace the production gate: the shipped
Operation must prove target resolution, exact Point preservation, native parity,
Color Mode and Brush behavior, clipping, explicit Selection Application, Background
and Linked Image rules, atomicity, save/close/reopen persistence, and structured
postconditions. Results return the exact Points, algorithm, normalized Brush/Color/
Ink/opacity, requested and actual coverage, every affected Cel/link, changed count,
and before/after content digest.

No command falls back to a fixed-Lua custom Bézier evaluator, polygon scanline fill,
GraphicsContext, Python renderer, or another Paint tool. Such a fallback would create
a second raster authority and erase the native differences the command names promise.

`paint blur` declares `deterministic` Operation Determinism and fixes Native Tool
Invocation to Aseprite's `blur` tool and Blur Ink. It accepts one non-empty ordered
Image Pixel `points` sequence as one Freehand gesture, Standard Paint Brush, integer
`opacity` in `0..255`, the operation-specific Freehand Algorithm `regular` or
`pixel-perfect`, and Tiled Mode `none`, `x`, `y`, or `both`. SPA preserves Point order
and multiplicity and delegates interpolation and Brush coverage to the native tool.

Blur accepts no Color Value, caller-selected Ink, mouse button, `dots`, random seed,
or generic convolution input. Native Blur Ink reads a 3-by-3 neighboring-pixel area,
extends its required source region by one pixel, blends through opacity, and uses
Tiled Mode for edge wrapping. The Tool Loop reads Tiled Mode from document state
rather than an `app.useTool` argument, so the fixed Lua Kernel must set the requested
native mode and restore the previous value around the invocation. This is
operation-local functional state, not a persistent session facility.

A direct 1.3.18.5 state probe read Tiled Mode `none`, changed it to `x` through the
native scripting command, and restored it to `none`. This proves the basic state seam;
the production slice must still prove restoration on every success and failure path.

A real Aseprite 1.3.18.5 discovery probe changed 133 pixels and produced zero pixel
difference between repeated executions against identical source content. Shipping
still requires exact editor parity for both algorithms, all Standard Paint Brushes,
all Tiled Modes and edges, opacity, supported Color Modes, Indexed Effective Palette,
actual source/affected bounds, clipping, explicit Selection Application, Background,
Linked Image, state restoration, atomicity, and save/close/reopen postconditions.
Results return exact Points, algorithm, normalized Brush/opacity/Tiled Mode, effective
Palette where applicable, requested source and actual affected regions, all affected
Cels/links, changed count, and before/after content digest.

`paint jumble` is an intended `native-stochastic` Operation using Aseprite's native
`jumble` tool, Jumble Ink, Freehand Controller, Standard Paint Brush, opacity, Tiled
Mode, random neighboring-pixel selection, and pointer velocity/direction. A discovery
probe confirmed that the scripted native tool changes pixels and is stochastic: 105
pixels changed and two identical requests differed at 98 pixels.

Aseprite 1.3.18.5 nevertheless constructs every scripted Pointer with zero velocity.
Jumble divides that velocity into its source-pixel displacement, so the scripted call
cannot express a core editor input. On that runtime, `paint jumble` is absent from the
Surface Manifest and `spa info` reports a typed Pointer Velocity Capability Gap with
runtime, tool, Pointer construction, and probe evidence. SPA does not publish a
fixed-zero subset, infer velocity from Point differences or timing, reuse Blur, or
implement random displacement in Lua/Python. A later native route must expose the
relevant pointer semantics and pass its own stochastic delegation, invariant, actual-
result, edge, state-restoration, and persistence gates before the descriptor ships.

Image Resize Transform is shared by `image resize` and Tileset Resize `scale`. It
requires exact positive integer `width/height` plus one typed Aseprite method:
`nearest-neighbor`, `bilinear`, or `rotsprite`. Zero/negative dimensions fail rather
than being clamped to 1, and unknown method values fail rather than falling through
to nearest-neighbor. The output retains its source Pixel Format and mask/transparent
value semantics. Nearest-neighbor samples stored values directly; rotsprite uses the
native stored-value algorithm. Neither requires a Palette for Indexed Images.
Bilinear interpolates native RGBA or Grayscale channels. For Indexed Images it
requires `palette_frame_number`, resolves that Effective Palette and Transparent
Color Index, converts indexes to RGBA with transparency, invokes Aseprite's bilinear
interpolation, and maps results through that Palette's native RGB Map without
dithering. The palette field is rejected for other method/Color Mode combinations.
The fixed Lua Kernel runs non-nearest native preprocessing and resize against a
source copy, then replaces the intended Image, preventing transparent-color fixup
from leaking source mutation on failure or through sharing. Resize Transform changes
the buffer only and never moves a Cel; linked targets still reduce to one shared
Image transformation and report every affected Cel. Results return requested and
actual size, method, Pixel Format, optional Palette Change/effective range/transparent
index, and before/after structural facts and content digest.

`image resize` composes the Transform with one required Image Resize Cel Position
Policy and applies to an existing Cel on an ordinary transparent Image Layer.
`keep` preserves every affected Canvas Pixel position. `pivot` accepts integer
`pivot_x/pivot_y` in the old Image Pixel space; the Point may be outside Image bounds
because it is a transform anchor, not a pixel access. For each axis the Kernel derives
the rational offset `pivot - pivot * new_size / old_size`, then applies the required
Pivot Rounding: `toward-zero`, `floor`, `ceil`, or `nearest-away-from-zero`. The same
integer offset moves every Cel that shares the transformed Image, preserving the
linked set; isolated movement first requires `cel unlink`. The result reports the
exact rational offsets, rounding mode, applied integer offsets, and every old/new Cel
position. Tilemap Cels use Tilemap Operations, Background Cels retain full-canvas
invariants, and Reference Layers use their floating-point bounds semantics, so all
three fail this Image-buffer Operation as unsupported Layer kinds. Buffer replacement
and all position changes occur in one all-or-nothing Mutation and are verified after
save/close/reopen.

`image crop` accepts one positive-size half-open Rectangle entirely contained in the
source Image Pixel bounds. It copies exactly that Rectangle into a same-Pixel-Format
Image whose origin is `(0,0)` and requires one Image Crop Cel Position Policy.
`preserve_canvas_pixels` moves every Cel sharing the Image by the Rectangle's `x/y`,
keeping retained pixels at their prior Canvas coordinates. `keep_cel_position` leaves
every position unchanged, so the retained region moves to each Cel's existing origin.
The shared Image is cropped once, the same offset is applied to its whole linked set,
and links remain intact; isolation requires `cel unlink`. Rectangle validation,
buffer replacement, and every position change form one all-or-nothing Mutation.
Tilemap, Background, Reference, and absent Cels fail under the same applicability rule
as `image resize`. Out-of-bounds padding, fill, and enlargement belong to Image Canvas
rather than introducing clipping or two meanings for Crop. Results include requested
and applied source Rectangle, old/new Image bounds, selected position policy, applied
offset, every affected Cel and link, Pixel Format, and before/after content digest,
all verified after save/close/reopen.

Image Canvas Transform is shared by `image canvas-resize` and Tileset Resize
`canvas`. It requires exact positive integer `width/height`, integer
`offset_x/offset_y` in target Image Pixel space, and an explicit Color Value compatible
with the source Pixel Format and applicable Palette facts. The Kernel fills a new
same-Pixel-Format Image, maps source `(0,0)` to the declared target offset, and copies
the intersection 1:1. Source pixels outside the target are discarded and uncovered
target pixels retain the fill. A request with no intersection remains a valid,
explicit fill-only transform. It performs no scaling, centering, Color Mode change,
Sprite canvas mutation, Selection application, or overlap guard. Tileset Resize
applies this exact Lua Kernel handler to each non-empty Tile in Tile Bitmap Pixel space
rather than owning a second copy/fill implementation.

`image canvas-resize` composes that buffer transform with one required Image Canvas
Cel Position Policy and applies to an existing Cel on an ordinary transparent Image
Layer. `keep_cel_position` leaves all affected Cel positions unchanged, so source
pixels move on the Sprite Canvas by the transform offset. `preserve_source_canvas`
subtracts the offset from every Cel position, preserving the Canvas coordinates of
every copied source pixel. A linked Image is transformed once, the same position
delta applies to every sharing Cel, and links remain intact; isolated behavior first
requires `cel unlink`. Tilemap, Background, Reference, absent, and non-Cel targets
fail. Buffer replacement and all position changes are one all-or-nothing Mutation.
Results include requested and actual dimensions, offset, fill, copied and discarded
source Rectangles, uncovered target region, every affected Cel/link and old/new
position, Pixel Format, and before/after content digest, all verified after
save/close/reopen.

`image flip` mirrors the complete target Image through Aseprite's native
`Image:flip`. The request requires `horizontal`, which mirrors left and right, or
`vertical`, which mirrors top and bottom; SPA does not expose the native omitted-axis
default. Because the transform preserves Image dimensions and Cel placement, it
supports existing Cels on ordinary Image, Background, and Reference Layers.
Background size/position/full-canvas invariants and Reference floating-point bounds
remain unchanged. A linked Image is flipped exactly once, every sharing Cel remains
linked and stationary, and the current Selection is not read or applied. Tilemap Cels
fail because a map mirror must operate on Tile Cells and Placement semantics rather
than packed Image pixels. The fixed Lua Kernel handler owns target resolution,
applicability, native invocation, observation, and result semantics; Python and
alternate Lua code do not implement a pixel-mirror loop. Results include axis,
dimensions, Layer kind, all affected Cels/links, unchanged position or Reference-bound
facts, and before/after content digest, verified after save/close/reopen.

Image Quarter-turn Transform is the shared buffer authority behind `image rotate`.
Aseprite 1.3.18.5 has no Lua `Image:rotate`, while its editor command targets a
Sprite canvas or Mask, so SPA does not route this Image operation through hidden
editor state. The request requires one Aseprite-aligned integer angle: `90` clockwise,
`-90` counterclockwise, or `180`. For source dimensions `W` by `H`, the fixed Lua
Kernel maps old Image Pixel `(x,y)` exactly to `(H-1-y,x)`, `(y,W-1-x)`, or
`(W-1-x,H-1-y)`, respectively. `90/-90` produce `H` by `W`; `180` retains `W` by
`H`. The transform copies stored values without interpolation, preserving Pixel
Format and mask/transparent semantics, and has no Cel placement or Selection
behavior. Arbitrary angles, normalization, and Python-side pixel loops are rejected.

`image rotate` composes that buffer transform with one required Cel Position Policy
for an existing Cel on an ordinary transparent Image Layer. `keep` leaves every
affected Cel position unchanged. `pivot` requires an integer Point in old Image Pixel
space, which may be outside the Image; the Kernel extends the same discrete mapping
to the Point and applies the exact integer delta `old_pivot - rotated_pivot` to every
Cel sharing the Image. No rounding rule is needed. The linked Image is transformed
once and sharing remains intact; isolated behavior first requires `cel unlink`.
Background, Reference, Tilemap, absent, and non-Cel targets fail because their native
full-canvas, floating-bound, or Placement semantics require separate operations.
Buffer replacement and all Cel position changes are one all-or-nothing Mutation.
Results include angle, explicit coordinate mapping, old/new dimensions, policy,
pivot and applied delta where present, every affected Cel/link and position, Pixel
Format, and before/after content digest, verified after save/close/reopen.

| Candidate command | Intended meaning |
| --- | --- |
| `spa image get` | Read Image facts and one complete canonical Pixel Region Snapshot for an explicit contained Rectangle. |
| `spa image replace` | Replace a complete non-Tilemap Image from a same-bounds, same-Color-Mode Pixel Region Snapshot or JSON Artifact. |
| `spa image resize` | Resize a regular transparent Cel Image through the shared Transform and an explicit `keep` or `pivot` Cel Position Policy. |
| `spa image crop` | Crop a regular transparent Cel Image to one contained Image Pixel Rectangle with explicit Canvas-position behavior. |
| `spa image canvas-resize` | Resize and reframe a regular transparent Cel Image without scaling, using explicit source offset, fill, and Canvas-position behavior. |
| `spa image flip` | Mirror a complete non-Tilemap Cel Image through native Aseprite semantics on a required horizontal or vertical axis. |
| `spa image rotate` | Rotate a regular transparent Cel Image by an exact `90`, `-90`, or `180` transform with explicit Cel-position behavior. |
| `spa paint apply` | Replace the stored values listed by one canonical Pixel Patch, with explicit clipping and Selection behavior. |
| `spa paint composite` | Composite a Pixel Region Snapshot through explicit Aseprite opacity, BlendMode, clipping, Selection, and Indexed Palette-basis semantics. |
| `spa paint pencil` | Draw one native Pencil gesture from an exact ordered Image Pixel Point sequence with explicit Standard Paint Brush, color, opacity, Ink, and Freehand Algorithm. |
| `spa paint eraser` | Apply one native Eraser gesture with explicit erase or foreground-to-background replacement behavior, Brush, opacity, Freehand Algorithm, clipping, and Selection. |
| `spa paint spray` | Apply native-stochastic Spray with ordered Image Pixel Points, explicit Standard Paint Brush, color, opacity, Ink, Spray Width, Spray Speed, clipping, and Selection. |
| `spa paint gradient` | Apply a deterministic native Linear or Radial Gradient with ordered axis Points, explicit colors, opacity, Dithering Matrix, Paint Fill matching, clipping, and Selection. |
| `spa paint curve` | Apply Aseprite's native Four-Point Bézier Curve with explicit Paint inputs when the runtime can express its controller headlessly. |
| `spa paint polygon` | Apply Aseprite's native Point-by-Point filled Polygon from ordered vertices when the runtime can express completion headlessly. |
| `spa paint contour` | Apply one native freehand gesture as an always-filled closed Contour through an independent delivery gate. |
| `spa paint blur` | Apply deterministic native Blur Ink through ordered Points, Standard Paint Brush, opacity, Freehand Algorithm, Tiled Mode, clipping, and Selection. |
| `spa paint jumble` | Apply native-stochastic Jumble with explicit pointer behavior when the runtime can express velocity and direction headlessly. |
| `spa paint line` | Draw a native Aseprite Line-tool stroke between two Image Pixel Points with explicit Standard Paint Brush, color, opacity, Ink, clipping, and Selection. |
| `spa paint rectangle` | Draw an outlined or filled native Aseprite Rectangle from explicit half-open Image Pixel bounds and shared Paint inputs. |
| `spa paint ellipse` | Draw an outlined or filled native Aseprite Ellipse from explicit half-open Image Pixel bounds and shared Paint inputs. |
| `spa paint fill` | Invoke native Paint Bucket from one Image Pixel seed with explicit color, opacity, Ink, tolerance, contiguous/connectivity, Refer To, Stop at Grid, clipping, and Selection. |

### `filter`

Owns Aseprite native Filter commands. This is a navigation projection within the
Raster Authoring Domain Module, not a bounded context, generic Effect model, Filter
DSL, or plug-in protocol. Aseprite's source groups these commands under
`commands/filters` and exposes shared Filter concepts such as target channels,
Selection, Cel/Frame scope, and tiled mode, while each command retains its own
parameters and behavior.

Aseprite's editor places some of these commands under Adjustments and some under FX;
those labels remain useful documentation subcategories rather than SPA top-level
groups or module boundaries. Replace Color and Invert Color are also native Filter
commands even though the editor menu places them directly under Edit.

Freehand Blur and Jumble stay under `paint`: they are native tools with a Brush,
Freehand Controller, sampled Points, and Tool Loop. They do not use the batch Filter
command lifecycle. Each Paint or Filter operation receives its own Descriptor,
Schema, fixed Lua Kernel handler, structured result, Capability Gap, and real-runtime
gate; the shared group never licenses arbitrary filter code or a universal request.

Every Filter descriptor requires a Filter-specific `cels_target`. Its `selected`
variant carries non-empty exact Layer addresses plus a non-empty set of unique
one-based Frame Numbers and resolves existing Cels in that Cartesian product. Missing
Cels are reported as empty timeline intersections and are never created. Every
explicitly selected Layer must accept Cels and satisfy Aseprite's native
`canEditPixels()` rule; otherwise preflight fails the whole Operation. Its `all`
variant has no Layer/Frame fields and resolves every existing Cel on a natively
pixel-editable Layer, reporting Layers excluded by that rule. Both require at least
one target Cel and neither inherits the active Cel, current range, or saved Filter
preference.

The fixed Lua Kernel installs and restores any temporary Aseprite range state. It
applies each Filter once per unique target Image and reports the requested timeline
intersections, resolved target Cels, unique Images, empty/excluded facts, and every
affected Linked Cel, including links outside a selected range. Pixel Selection
Application remains an orthogonal explicit input. This shared Filter value does not
become a generic cross-command Selector.

Filter descriptors also require typed `channels`. The `components` form contains a
non-empty unique set: RGB accepts `red`, `green`, `blue`, and `alpha`; Grayscale accepts
`gray` and `alpha`; Indexed component interpretation accepts the RGBA names through an
explicit Palette basis. The exclusive `index` form is available only for Indexed
Sprites and Filters that demonstrably process stored Palette Indexes. Each operation
rejects unsupported or no-op channels even when Aseprite's internal integer mask can
encode them. Requests never inherit native defaults or editor button state, and Alpha
fails preflight if any resolved target is a Background Cel. The Lua Kernel owns the
named-channel-to-native-flag mapping; no public raw mask exists. Indexed application
destination and Palette basis are specified separately by each applicable Filter
contract.

Brightness/Contrast and Hue/Saturation additionally require `application` because
Aseprite's `FilterWithPalette` selects materially different mutations from ambient
state. `pixels` requires Filter Cels Target and optional Selection Application; on an
Indexed Sprite it also requires `palette_frame_number`, clears Palette Picks, and
materializes the explicit Selection or an all-canvas mask so native execution changes
pixels rather than the Palette. `indexed-palette-entries` targets one exact Palette
Change and `all` or non-empty explicit Palette Indexes, rejects Cel/Selection fields,
and preserves every stored pixel index. `rgb-palette-colors` targets one exact Palette
Change, non-empty Palette Indexes, Filter Cels Target, and optional Selection; it
changes those Entries and replaces exact old-Palette-color matches in participating
RGB pixels. Grayscale accepts only `pixels`. Other Filters have fixed pixel meaning
and omit `application`.

The Lua Kernel sets and restores active Frame, Palette Picks, Cel range, and pixel
Selection for these native branches. A private active-image execution anchor for an
Indexed Palette-only branch is not exposed as a target and must be proven not to
mutate Cel content. Results independently report Palette and Image changes, affected
ranges and relationships, and the declared Palette basis. No branch inherits editor
state or reimplements Filter math.

| Candidate command | Intended meaning |
| --- | --- |
| `spa filter brightness-contrast` | Apply deterministic native Brightness/Contrast with required `-100..100` integer percentages, effective component Channels, and explicit Filter Application. |
| `spa filter hue-saturation` | Apply native HSL/HSV multiply or add adjustment, distinct Grayscale Lightness, and conditional Alpha through explicit Filter Application. |
| `spa filter color-curve` | Apply native linear Color Curve Points to explicit component or Indexed Index Channels through a declared Palette basis. |
| `spa filter replace-color` | Apply native per-component or stored-Index matching with explicit Color Values, `0..255` Tolerance, targets, and Selection. |
| `spa filter invert-color` | Apply native component or stored-Index inversion with explicit Channels, Palette validity, targets, and Selection. |
| `spa filter outline` | Apply Aseprite's native Outline FX with explicit placement, matrix, colors, channels, and tiled mode. |
| `spa filter convolution-matrix` | Apply one uniquely resolved native Convolution Matrix Resource when the runtime honors explicit Channels and missing-resource failures. |
| `spa filter despeckle` | Apply Aseprite's native per-channel Median Filter with explicit dimensions, Channels, Tiled Mode, targets, and Selection. |

#### `spa filter brightness-contrast`

Requires integer `brightness` and `contrast` in the inclusive range `-100..100`.
Both fields are explicit; zero/zero is a valid reported no-op. RGB and Indexed
component interpretation accept any non-empty subset of `red`, `green`, and `blue`;
Grayscale requires `gray`. `alpha` and `index` are rejected because Aseprite's native
implementation does not modify them.

The Operation uses the accepted `pixels`, `indexed-palette-entries`, or
`rgb-palette-colors` Filter Application where valid for the Sprite Color Mode. It
accepts no Tiled Mode, gamma, transfer curve, pivot, alternate color space, or custom
formula. The fixed Lua Kernel invokes the native command and retains authority for its
percentage conversion, contrast-before-brightness mapping, clamp, integer conversion,
Palette matching, and Indexed RGB Map quantization. The structured result reports
percentages, effective Channels/Application, target and Palette facts, changed Entries,
unique Images and affected Cels, changed pixels/indexes and bounds, and persisted
before/after observations. Shipping remains gated by complete real-runtime parity and
rollback evidence rather than the source inspection alone.

#### `spa filter hue-saturation`

Uses a conditional adjustment contract. `hsl-multiply` and `hsl-add` require integer
`hue` in `-180..180` plus `saturation` and `lightness` in `-100..100`.
`hsv-multiply` and `hsv-add` use the same ranges but name the third component `value`.
Grayscale uses a separate multiplicative `grayscale` adjustment with only
`lightness: -100..100`. An `alpha: -100..100` value is required exactly when Alpha
is selected. Every governed zero value is valid and can form a reported no-op.

RGB and Indexed component interpretation accept non-empty subsets of `red`, `green`,
`blue`, and `alpha`; Grayscale accepts `gray` and `alpha`; `index` is invalid. A color
adjustment exists exactly when an RGB component is selected, Grayscale adjustment
exists exactly when Gray is selected, and Alpha exists exactly when Alpha is selected.
Cross-branch or ignored fields fail validation. Valid Color Modes use the accepted
Filter Application branches, with Background Alpha and Palette rules applied before
mutation.

The fixed Kernel maps the four public color modes to native HSL/HSV multiply/add
values and rejects unknown strings before Aseprite's fallback. Native HSL/HSV
conversion, Hue wrap, relative/additive calculation, Alpha behavior, clamping,
component projection, Palette matching, and RGB Map quantization remain authoritative.
No Tiled Mode, stored-Index, custom matrix, or transfer-function input exists. The
command is absent from a runtime Surface Manifest until real headless tests prove all
four modes—including the under-documented HSL+/HSV+ paths—plus every applicable
Application and persistence gate.

#### `spa filter color-curve`

Requires `points` with 1..256 `{input, output}` objects. Both fields are integers in
`0..255`, and inputs are strictly increasing. A single Point expresses a constant
mapping; no endpoint pair is required. Native Linear interpolation extends the first
and last outputs outside their Point interval. Unsorted, duplicate-input, empty, or
out-of-range Points fail rather than being reordered or given implicit meaning.

RGB supports non-empty `red`/`green`/`blue`/`alpha` component subsets and Grayscale
supports `gray`/`alpha`. Indexed requires `palette_frame_number` and either an RGBA
component subset, using that Frame's Effective Palette and RGB Map, or exclusive
`index`, applying the curve to stored indexes and clamping to the Palette's valid
Entry range. The command is always a pixel Filter: it requires Filter Cels Target,
accepts explicit Selection Application, has no Filter Application union, and cannot
change Palette Entries.

The fixed Lua Kernel maps the canonical Point list into the native command. Aseprite
owns interpolation, integer division, endpoint extension, clamping, component
projection, Palette lookup, and RGB Map quantization. No Tiled Mode, empty shorthand,
Spline, Bézier, formula, gamma, separate LUT, or hidden editor curve is accepted.
Results return Points, Channels, Palette basis, target/Selection facts, unique Images,
all affected Cels, change counts/bounds, and persisted observations. Real native
parity, target, rollback, restoration, and save/reopen matrices gate delivery.

#### `spa filter replace-color`

Requires `from`, `to`, and integer `tolerance` in `0..255`. RGB uses compatible RGBA
Color Values and non-empty `red`/`green`/`blue`/`alpha` component subsets. Grayscale
uses Grayscale Color Values and `gray`/`alpha`. Native matching compares each selected
component independently with the same Tolerance, requires all comparisons to pass,
and preserves every unselected component.

Indexed requires `palette_frame_number`; both `index` and `components` require valid
Palette Index Color Values for `from` and `to`. Index mode compares stored index
distance and writes the destination Index. Component mode resolves both Entries to
RGBA through the Effective Palette, applies the selected component predicate and
replacement, and uses the native RGB Map for output. RGBA-to-Index best-fit input is
not accepted because its effective Palette Entry can be declared directly.

The command always requires Filter Cels Target, accepts Selection Application, never
changes Palette Entries, and has no Filter Application union. Equal `from` and `to`
is valid but can normalize neighboring values at positive Tolerance; results therefore
separate matched and changed counts. No Tiled Mode, aggregate/perceptual distance,
per-channel Tolerance, palette growth, dithering, or custom quantizer is accepted.
Aseprite owns all comparisons, composition, Palette lookup, and RGB Map behavior.
Results include resolved colors and Palette basis, target/Selection and linked facts,
counts/bounds, and persisted observations; real-runtime parity and failure gates apply.

#### `spa filter invert-color`

Requires only explicit Filter Channels. RGB accepts non-empty
`red`/`green`/`blue`/`alpha` subsets and Grayscale accepts `gray`/`alpha`. Indexed
requires `palette_frame_number` plus either an RGBA component subset, resolved and
quantized through that Effective Palette and RGB Map, or exclusive `index` processing
using native `255-index` stored-byte inversion.

Native Index inversion does not clamp to Palette size. Before invocation the Kernel
checks every participating source and resulting Index after Cel and Selection
resolution; any value without an Entry in the declared Effective Palette fails the
whole Operation with source, inverted, Palette, and location facts. SPA does not
expand the Palette, clamp, or switch interpretation.

The command always requires Filter Cels Target, accepts Selection Application, has no
Filter Application union, and never changes Palette Entries. Background Alpha and all
shared target, link, transaction, restoration, and persistence rules apply. No Tiled
Mode, strength, blend, color-space, center, or custom function exists. Aseprite owns
the inversion and Indexed quantization. Results report Channels, Palette and target
facts, Images/Cels, counts/bounds, and persisted output. Two-pass restoration is an
observed property of byte-component and valid Index paths, not a promise for quantized
Indexed components.

#### `spa filter outline`

Requires `place` as `inside` or `outside`, explicit compatible `outline_color` and
`background_color` values, Filter Channels, Filter Cels Target, and Tiled Mode
`none`/`x`/`y`/`both`. It accepts explicit pixel Selection Application. Background
Color is part of native candidate classification rather than an editor canvas
setting: RGB and Grayscale treat zero-Alpha or exact-equal pixels as background,
while Indexed stored-Index mode uses exact Palette Index equality.

Outline Matrix is a typed operation-specific union. `preset` accepts `none`,
`circle`, `square`, `horizontal`, or `vertical`. `custom` accepts a non-empty unique
set of `top-left`, `top`, `top-right`, `left`, `right`, `bottom-left`, `bottom`, and
`bottom-right`, naming neighbor positions around each candidate Image Pixel. The
fixed Lua Kernel maps these positions to Aseprite's native 3-by-3 bits. It exposes no
raw integer or center position: source inspection and a real center-only probe show
that the center cannot satisfy the opposite-classification predicate and has no
effect. The `none` preset is the canonical empty Matrix and a valid reported no-op.

RGB uses RGBA Color Values with non-empty compatible component Channels; Grayscale
uses Grayscale values and components. Selected components come from Outline Color,
and unselected components retain the candidate pixel's values under native behavior.
Indexed stored-Index execution requires `palette_frame_number`, exclusive `index`
Channels, and valid Palette Index values for both colors in that Effective Palette.

On Aseprite 1.3.18.5, Indexed component execution is a version-specific Capability
Gap. The command wrapper converts the requested color to a Palette Index, after which
the Filter implementation reads that integer as packed RGBA. A real 5-by-5 headless
probe produced the expected four-pixel Index cross but no outline for RGBA or
Red-plus-Alpha Channels. SPA neither switches Channels nor supplies a Lua/Python
renderer. A supported runtime can publish that combination after its parity gate.

The Operation has no Filter Application and never mutates Palette Entries. It accepts
no thickness, radius, distance metric, blend mode, generic convolution, arbitrary
Matrix dimensions, or caller code. Wider outlines use explicit repeated native Steps
in an Operation Plan. Aseprite owns classification, placement, neighborhood, edge,
component, bounds, and Indexed-write semantics. Results report canonical and native
Matrix facts, colors, placement, Channels/Palette, Tiled Mode, targets/Selection,
unique Images and all affected Cels, candidate/matched/changed counts, resulting
bounds, and persisted content. Shipping requires preset and asymmetric-custom parity,
Inside/Outside, edge modes, supported Color Modes, classification, Selection,
Background/linked targets, no-op, rollback, restoration, and save/reopen gates.

#### `spa filter convolution-matrix`

This intended deterministic pixel Filter requires one exact `resource_name`, typed
Filter Channels, Tiled Mode `none`/`x`/`y`/`both`, Filter Cels Target, and optional
Selection Application. It has no Filter Application and does not mutate Palette
Entries. Runtime discovery reports Convolution Matrix Resource names, source
locations, duplicate-name facts, and declared default Channels through `spa info`.
The requested name must resolve exactly once; missing or ambiguous names fail before
mutation with the available or conflicting Resource facts.

Resource defaults remain discovery facts and never replace explicit Channels. RGB
accepts non-empty red/green/blue/alpha component subsets; Grayscale accepts
gray/alpha. Indexed support requires `palette_frame_number` and a proven native
component or exclusive stored-Index path. Every resulting stored Index is validated
against its applicable Effective Palette in the Staged Sprite File before Target
Commit; invalid output fails with Palette, Frame, Image, Cel, and pixel-location
facts rather than being clamped, remapped, or accepted.

Aseprite owns Resource parsing, coefficient precision, center, divisor, bias,
transparent-neighbor handling, arithmetic, component projection, edge sampling,
clamping, Palette lookup, and RGB Map quantization. The request accepts no inline
coefficients, arbitrary dimensions, divisor/bias override, generic kernel data,
formula, code, or plug-in reference. SPA does not implement convolution in Python or
another Lua algorithm.

Aseprite 1.3.18.5 exposes a documented `channels` argument but its command never
applies it to the Filter manager. The non-UI path also never installs the Resource's
declared default Channels, and a missing Resource finishes successfully with no
Matrix. A real probe applied the built-in `brightness` Resource to RGBA
`(10,20,30,40)`; Red and Alpha requests both returned `(18,28,38,48)`, while an
unknown name returned the unchanged pixel with process success.

Consequently this Operation is absent from the 1.3.18.5 Surface Manifest and
`spa info` reports a typed Convolution Matrix Channels Capability Gap. SPA does not
publish an all-component, fixed-Resource, RGB-only, or silent-no-op subset. A later
runtime must prove resource resolution, Channel control/default independence, Tiled
Mode, targets, Selection, Color Modes, Indexed validity, Background/linked behavior,
rollback, restoration, and persistence before publishing the Descriptor. Results
then report resolved Resource facts, declared/default and requested Channels, Tiled
Mode, Palette basis, target/Selection and relationship facts, counts/bounds, and
persisted content.

#### `spa filter despeckle`

Keeps Aseprite's Despeckle command name and declares deterministic native Median
Filter behavior. The request requires integer `width` and `height`, each in the
editor's inclusive `1..100` range, typed Filter Channels, Tiled Mode
`none`/`x`/`y`/`both`, Filter Cels Target, and optional Selection Application. It has
no Filter Application and never mutates Palette Entries. Values outside the editor
range fail before native invocation instead of being clamped or reaching the raw
allocation path.

Odd and even dimensions are valid. Aseprite anchors the rectangular window at
`floor(width/2), floor(height/2)` and selects sorted element
`floor(width*height/2)`, the upper median for an even count. Tiled Mode wraps the
requested axes; `none` repeats edge pixels. A 1-by-1 window is a valid reported
no-op.

RGB accepts non-empty red/green/blue/alpha component subsets, and Grayscale accepts
gray/alpha. Indexed requires `palette_frame_number` and either exclusive `index`,
which sorts stored Palette Index values, or RGBA `components`, which resolves the
Effective Palette, calculates selected component medians, preserves unselected
components, and quantizes through the RGB Map.

Aseprite 1.3.18.5 has a combination-specific Indexed component defect. When Green is
not selected, the native code performs a second Palette lookup using an already
packed RGBA value and writes zero instead of preserving the candidate's Green. A
discriminating 3-by-1 probe made the correct and corrupted colors separate Palette
Entries: Red-only produced the corrupted Entry 5 instead of Entry 4, while Green
produced Entry 6, Index produced median Entry 2, and 1-by-1 preserved Entry 2.

Accordingly an Indexed component request on that runtime must include Green; any
non-empty subset without it reports a typed Capability Gap before mutation. SPA does
not add Green, switch to Index, repair pixels, or invoke another renderer. The
working RGB, Grayscale, Index, and Green-containing component paths remain eligible
for their own delivery gates.

Aseprite owns neighborhood construction, even-window anchoring, edge repetition and
Tiled wrapping, sorting, median choice, transparency, component preservation,
Palette lookup, and RGB Map quantization. No strength, percentile, iteration, radius,
shaped/weighted window, color-distance rule, alternate median, statistic, or caller
code is accepted. Results report dimensions/anchor/sample count/median rule,
Channels/Palette/Tiled Mode, targets/Selection and linked Images/Cels, change
counts/bounds, and persisted content. Delivery tests every size boundary and parity,
supported Channel branch, edge mode, no-op, target kind, failure, restoration, and
save/reopen result.

### `palette`

Owns Aseprite Palette Changes, Palette entries, Transparent Color Index, Color
Quantization, and Palette facts used by Change Color Mode. `Sprite.palettes` is an
ordered set of change points rather than an independent Palette per Frame. A Palette
Change begins at its one-based `palette_frame_number`; the Effective Palette for any
requested `frame_number` is the latest change at or before that Frame and applies
until the next change or the last Frame. Inspection returns that inclusive effective
Frame Range and keeps each zero-based entry Palette Index distinct from its RGBA Color
Value.

Read Operations can resolve an Effective Palette from any `frame_number`. Entry
mutation, resize, and import target an existing change point by its exact
`palette_frame_number`, so a multi-Frame effect is never hidden. Aseprite 1.3.18.5
does not expose Palette Change creation or deletion through its public Lua/editor
surface: the installed runtime capability report records this gap, and the catalog
does not promise `palette add` or `palette remove`. SPA does not use private C++ APIs,
patch `.aseprite` chunks, or generate Lua to simulate them. New native evidence can
reopen those lifecycle Operations. No Palette collection position, process-local
object ID, UUID, or universal Selector is a Palette identity.

Palette content editing keeps Aseprite's Palette Entry mutation and Remap Colors
concepts distinct. `palette set` changes RGBA values at existing Palette Indexes and
preserves the indexes stored in pixels, intentionally recoloring their rendered
result. `palette reorder` atomically reorders entries and remaps Indexed pixels so
their resolved RGBA colors remain stable. Its discriminated `scope` is
`palette-change` or `sprite`. `palette-change` requires an exact
`palette_frame_number`, applies to that effective Frame Range, keeps the Sprite-wide
Transparent Color Index fixed, and refuses an Image that is also referenced by a
Cel outside the range; callers use explicit `cel unlink` before retrying. `sprite`
applies the same valid Entry permutation to every Palette Change and every Indexed
Image and can remap the Transparent Color Index. Neither scope silently expands or
unlinks a Cel.

`palette remap` follows Aseprite's native Sprite-wide Remap Colors concept. It
receives an explicit old-to-new index mapping, rewrites every Indexed Image and the
global Transparent Color Index, and accepts no Frame Range or Palette Change target.
Every mapped pixel destination must exist in the Effective Palette for its Frame,
and the resulting Transparent Color Index must exist in every Palette Change.
Palette growth declares the colors of every new Entry. Shrink refuses any removed
index still used by an applicable pixel or the Transparent Color Index; the caller
remaps those indexes first. Results report the declared scope and exact mapping,
changed Palette facts, all affected Images/Cels/Frames, and any Transparent Color
Index change. Typed failures identify cross-range shared Images or invalid mappings.

`palette color-quantization` follows Aseprite's native "Create Palette from Current
Sprite (Color Quantization)" command. It requires one exact existing
`palette_frame_number`, `max_colors` in `1..256`, explicit `with_alpha`, and an
explicit `rgb_map_algorithm` of `default`, `rgb5a3`, or `octree` plus the native
`new_layer_blending_method` boolean. Explicit `default` resolves to Octree. Omitted,
unknown, numeric, and case-variant algorithms fail before native fallback, and Color
Best Fit Criteria is not an input to this native Operation. The fixed Lua Kernel
activates the addressed Frame, clears Palette Picks, sets the requested blend method,
invokes native `ColorQuantization` with `useRange=false`, and restores invocation-local
state. The native operation renders every Sprite Frame and replaces the complete
Current Palette selected by that Frame; it does not add a Palette Change. The request
accepts no Frame, Tag, Layer, Selection, Palette-Pick, or `useRange` scope. Results
report the exact Palette Change and its Effective Frame Range, all-Frame rendering
scope, requested limit, actual size, Alpha choice, requested/effective algorithm,
blend method, complete Entries, and every potentially rerendered Frame. A real
Aseprite 1.3.18.5 probe proved the preference can be set to both values and restored,
and retained one Palette Change while producing the requested two-color Palette. The
seam remains private to this functional Operation; it does not create a general
preference-management contract.

| Candidate command | Intended meaning |
| --- | --- |
| `spa palette list` | List Palette Changes with `palette_frame_number` and inclusive effective Frame Range. |
| `spa palette get` | Resolve a `frame_number` to its Effective Palette and read Palette Index/RGBA entry pairs. |
| `spa palette set` | Recolor existing Palette Entries at an exact `palette_frame_number` while preserving stored pixel indexes. |
| `spa palette reorder` | Preserve rendered colors while reordering one Palette Change or every Palette Change under an explicit domain scope. |
| `spa palette remap` | Apply Aseprite-aligned Sprite-wide Remap Colors through an explicit old-to-new Palette Index mapping. |
| `spa palette resize` | Grow with explicit new Entry colors, or shrink only when removed indexes are unused and not transparent. |
| `spa palette import` | Import entries into an exact existing Palette Change from a supported Artifact format. |
| `spa palette export` | Export the Effective Palette for a requested Frame as a Palette Artifact with resolved source facts. |
| `spa palette color-quantization` | Replace one existing Palette Change using Aseprite Color Quantization over every rendered Sprite Frame. |

### `selection`

Owns explicit serializable Aseprite Selection values and their native pixel-Mask
operations. Selection is Canvas Pixel data, not the target-addressing mechanism for
Layers, Frames, Cels, or other objects and not persistent Sprite File state. The Lua
Kernel can materialize a request value as `Sprite.selection` while one Operation
runs, but commands never rely on an active Selection from another invocation.
Selection-consuming Paint, Image, copy, move, erase, and transform Operations carry
the Selection explicitly. Omission means no restriction; an explicit empty Selection
selects zero pixels; an explicit all-canvas Selection selects the whole canvas.
The canonical encoding is `empty`, `all` with an explicit Canvas Rectangle, or a
binary `mask` with tight bounds and rows of absolute Canvas Pixel `y` plus sorted,
merged `{x, length}` runs. Geometry is creation intent rather than another stored
variant. Inline values and JSON Artifacts with role `selection-mask` use the same
schema. PNG output is a separate non-authoritative Preview Artifact.

| Candidate command | Intended meaning |
| --- | --- |
| `spa selection create` | Create and normalize an explicit Selection from supported geometry or binary Mask data. |
| `spa selection combine` | Return the union, intersection, subtraction, or xor of explicit Selection values. |
| `spa selection invert` | Return a Selection inverted within an explicit canvas Rectangle. |
| `spa selection grow` | Grow an explicit Selection using declared native semantics. |
| `spa selection shrink` | Shrink an explicit Selection using declared native semantics. |
| `spa selection transform` | Transform an explicit Selection without moving Sprite pixels. |
| `spa selection validate` | Validate Selection bounds, encoding, and Canvas Pixel semantics. |
| `spa selection export` | Write the canonical Selection Encoding as a validated JSON Selection Mask Artifact. |
| `spa selection preview` | Render a non-authoritative PNG Preview Artifact for human inspection. |

### `slice`

Owns Aseprite Slice lifecycle, ordered Slice Keys, and user properties. Each Slice
Key starts at a one-based Frame Number and contains Canvas Pixel bounds plus an
optional Slice-local center Rectangle and pivot Point. Reads preserve all explicit
Keys and report their inclusive effective Frame Ranges rather than flattening a
Slice into one static Rectangle. An existing Slice is addressed by current one-based
`slice_index` or unique `slice_name`; neither form is a Persistent Identity. For
Aseprite 1.3.18.5, a fixed Lua Kernel handler invokes native `listSlices` exporter
metadata and normalizes it into this complete read model. The temporary vendor JSON
and texture are private data files, not an alternate public result or generated Lua.

| Candidate command | Intended meaning |
| --- | --- |
| `spa slice list` | List every Slice with current index, complete properties, all explicit Keys, and effective Frame Ranges. |
| `spa slice get` | Read one Slice by current index or unique name with the same complete Key model. |
| `spa slice add` | Add a named Slice with one explicit initial Slice Key at Frame 1 and optional center, pivot, and user data. |
| `spa slice remove` | Remove one Slice addressed by current index or unique name. |
| `spa slice set` | Set name or user data; set bounds, center, or pivot only when the Slice has exactly one Key at Frame 1. |

Aseprite 1.3.18.5's public Lua Slice API exposes no arbitrary Slice Key collection
or lifecycle. The UI-only `SliceProperties` command is not a batch automation seam.
The Surface Manifest therefore contains no `slice key add`, `slice key set`, or
`slice key remove` descriptor for that runtime, and `spa info` reports the Capability
Gap. SPA does not fill it with GUI automation, private C++ commands, direct
`.aseprite` editing, Python-side semantics, or generated ordinary-operation Lua.

### `tileset` and `tilemap`

These are separate navigation concepts but are expected to share one tile-authoring
Domain Module. `tileset` owns reusable Tile definitions and Tileset properties;
`tilemap` owns Tile placement in tilemap Layers and coordinate-space-aware
inspection. Direct Tileset targets use current one-based `tileset_index` or unique
`tileset_name`; Layer-scoped Operations can resolve the Tileset referenced by an
exactly addressed Tilemap Layer. Aseprite's persisted `base_index` is a display
offset, never an address. Native Tile Indexes are zero-based, with the non-removable
Empty Tile at 0. Persistent authoring references use a caller-supplied, Tileset-scoped
`tile_key` stored under the versioned `aigengame.spa` Tile properties namespace.
Existing unkeyed or duplicate-keyed Tiles remain fully inspectable without implicit
metadata writes.

Adding a Tilemap Layer with `tileset.create` creates and binds one new Tileset and
returns both resulting objects. `tileset.share` resolves exactly one existing Tileset
before mutation. If Aseprite's native Tilemap Layer creation produces an implicit
Tileset, the fixed Lua Kernel binds the new Layer to the selected shared Tileset and
deletes only that newly created orphan inside the same all-or-nothing Mutation. It
then rereads the Layer UUID, Tileset relationship, and total Tileset collection after
save/close/reopen. No current editor selection, preference, active Tileset, or
Tileset 0 supplies a default. The Sprite's existing initial Raster Layer is preserved;
removing it is a separate `layer remove` Operation.

`tileset remove` resolves every Tilemap Layer that references its exact target before
mutation. Any reference fails with `TILESET_IN_USE`, returns the complete referencing
Layer facts, and performs no mutation. SPA does not invoke Aseprite's native implicit
reassignment of those Layers to Tileset 0. An agent can compose explicit Layer
rebinding Operations followed by removal in one Operation Plan; both entrypoints
reuse the same Lua Kernel semantics. Successful removal reports the removed Tileset,
the complete old-to-new Tileset Index mapping, and every surviving Tilemap Layer
binding, then verifies those facts after save/close/reopen. This targeted lifecycle
rule does not introduce a general orphan scanner or garbage collector.

`layer set-tileset` is a named Operation rather than an ordinary property update. It
exactly resolves one Tilemap Layer and one target Tileset, then requires a Tile
Rebinding Map. `by_key` maps every used non-empty source Tile Key to the identical,
unique target Key. `explicit` maps every used source Key to one target Key or Empty
Tile. Empty remains Empty; raw Tile Indexes, incomplete maps, unkeyed or
duplicate-keyed used source Tiles, and missing or ambiguous target Keys fail before
mutation. The request also declares `require_equal` or `use_target` as its Tileset
Grid Policy. The first refuses different Grids. The second keeps Tile Cell
coordinates and Cel positions, performs no resampling, and accepts the target Grid's
effective Grid and Canvas coverage. The fixed Lua Kernel rewrites all Placements in
every Cel of the Layer while preserving X/Y/diagonal flags, then changes the Tileset
reference in the same all-or-nothing Mutation. Results include the complete
Key-to-Index translation, affected Cels and Cells, old/new effective Grids and Canvas
coverage, and the final binding verified after save/close/reopen. The public command
belongs to Layer lifecycle while the tile-authoring Domain Module implements it.

An existing Tileset Grid is read-only in Aseprite's supported Lua API and is not a
field of `tileset set`. `tileset resize` models Grid change as replacement: its fixed
Lua Kernel handler constructs a new Tileset with the requested Grid, transforms and
preserves Tile Images, Keys, data, and Properties under the Operation's declared
policies, rebinds every referencing Tilemap Layer by reusing the same Core Operation
Semantics as `layer set-tileset`, and removes the old unreferenced Tileset in the same
all-or-nothing Mutation. It returns old and replacement Tileset facts, complete
Tileset Index changes, Layer relationships, and affected Tile/Cel facts without
claiming persistent Tileset identity.

The request requires two orthogonal policies. Tile Image Transform is either `scale`,
which applies the shared `image resize` interpolation and Color Policy semantics to
every non-empty Tile at the target Grid size, or `canvas`, which applies the shared
Image Canvas Transform in Tile Bitmap Pixel space with explicit target size, source
offset, and compatible fill. Empty Tile is recreated by native Tileset
construction. Tile order, Keys, data, and all accepted Properties are preserved.

Tileset Resize Cel Position Policy is either `keep_canvas_position`, which leaves
each referencing Cel's Canvas Pixel position unchanged, or `preserve_grid_position`,
which requires each position to be exactly divisible by the old tile width/height and
maps that integral Grid coordinate to the new Grid without rounding. Both preserve
Tilemap Image dimensions in Tile Cells, all Placement Keys and flags, and Cel content;
neither resamples or clips the Tilemap, changes the Sprite canvas, or discards coverage
outside it. The new Tileset Grid origin is Aseprite's fixed `(0,0)`. Internal
rebinding uses the accepted `by_key` plus `use_target` semantics. Results enumerate
each Tile transform, every old/new Cel position, effective Grid and Canvas coverage,
and the final Tileset/Tile/Placement facts. The `scale` variant remains gated on the
shared Image Resize semantic and its Indexed Color rules, and every variant requires
a real Aseprite save/close/reopen vertical slice before this catalog candidate ships.
A Sprite-level resize remains distinct and cannot alter a Tileset Grid as a hidden
`tileset set` side effect.

| Candidate command | Intended meaning |
| --- | --- |
| `spa tileset list` | List every Sprite Tileset, including current index, properties, and referencing Tilemap Layers. |
| `spa tileset get` | Read one Tileset's Grid, Base Index, properties, Tiles, Tile Keys, and current Tile Indexes. |
| `spa tileset add` | Add a named Tileset with an explicit Grid and Base Index. |
| `spa tileset remove` | Remove one exactly addressed, unreferenced Tileset; otherwise fail with complete referencing Layer facts. |
| `spa tileset set` | Set supported writable Tileset properties; Grid is explicitly excluded. |
| `spa tileset resize` | Replace one Tileset with a declared Grid while transforming Tiles and rebinding all referencing Layers atomically. |
| `spa tileset tile get` | Inspect a Tile by Tile Key or current Tile Index. |
| `spa tileset tile add` | Append a non-empty Tile from typed Image input with a required unique Tile Key; no insertion position is accepted. |
| `spa tileset tile set-key` | Explicitly assign or change the Tile Key of a non-empty Tile. |
| `spa tileset tile set` | Set a keyed Tile's Image or native user properties while preserving unrelated properties. |
| `spa tileset tile remove` | Remove a keyed non-empty Tile, requiring an explicit Tile Key or Empty Tile replacement when used and remapping every affected Placement. |
| `spa tileset tile reorder` | Reorder all non-empty Tiles from one complete Tile Key permutation and remap every Placement. |
| `spa tileset validate` | Check Grid dimensions, names, indexes, references, Tile Keys, and declared tile rules. |
| `spa tilemap get` | Read topology/usage summaries by default or a complete Tile Region Snapshot for an explicit region or Artifact projection. |
| `spa tilemap set` | Replace a complete Tile Cell Rectangle from a Tile Region Snapshot; omitted Cells become Empty. |
| `spa tilemap patch` | Change only explicitly listed Tile Cells and leave all other Placements unchanged. |
| `spa tilemap fill` | Fill a bounded Cel-local Tile Cell Rectangle with one Placement Value. |
| `spa tilemap validate` | Check map bounds, references, coordinate spaces, and declared layout rules. |

A Tilemap target is exactly one Tilemap Layer plus one one-based Frame Number and
must already contain a Cel. The Tilemap Cel's Image dimensions are measured in Tile
Cells; zero-based `tile_x/tile_y` and operation Rectangles are local to that Image.
Inspection also returns the Cel's Canvas Pixel position, Tileset Grid, effective Cel
Grid, and computed Canvas coverage. Mutation Placement Values are discriminated as
`empty` or `tile` with Tile Key and explicit X/Y/diagonal flip booleans. Inspection
also returns current Tile Index and preserves a native unkeyed placement with
`tile_key: null`. Packed integers, Base Index, and bare Tile Index are never mutation
inputs. Missing Cels fail rather than being created implicitly; `cel add` and a
Tilemap write can be composed in an Operation Plan. Out-of-bounds regions fail unless
the specific Operation exposes explicit clipping and returns the applied Tile Cell
Rectangle.

Default `tilemap get` returns Cel dimensions, Grid and Canvas mapping, Tile usage, and
other complete topology summaries without expanding Cells. A region request returns
a Tile Region Snapshot: the Rectangle plus every non-empty Placement in ascending
`tile_y`, then `tile_x` order at absolute Cel-local coordinates; all omitted Cells are
explicitly Empty. Duplicate or out-of-Rectangle entries fail. `tilemap set` consumes
the same canonical structure with keyed mutation values and replaces the whole
Rectangle. `tilemap patch` uses unique explicit Cells and leaves omissions unchanged.
`tilemap fill` writes one Placement Value and has no pattern language. When complete
Cel data exceeds the inline Domain Bound, an explicitly selected JSON Artifact uses
the same Snapshot structure. Every result reports requested and covered Rectangles
and completeness; exceeding a bound never truncates or returns partial success.

Tile removal first resolves every Tilemap Layer and Cel sharing the Tileset. If the
target Tile is unused, removal shifts every higher native Tile Index down by one and
rewrites those Placements accordingly. If it is used, the request must also choose
another Tile Key in the same Tileset or the Empty Tile for those cells. The fixed Lua
Kernel applies the complete mapping and deletion as one all-or-nothing Mutation,
preserves X/Y/diagonal flags, rereads the resulting Key-to-Index relationships, and
reports every affected Layer, Cel, and Tile Cell. It never performs visual matching,
deduplication, or silent clearing.

Tile reorder requires `tile_key_order` to contain every non-empty Tile Key exactly
once. Empty Tile stays at Index 0 and Base Index does not change. A missing, extra,
or duplicate request Key, or any unkeyed or duplicate-keyed Tile in the Tileset,
fails before mutation. The fixed Lua Kernel moves each Tile's Image, color, data,
Tile Key, and unrelated Properties together, applies the complete Index mapping to
all shared Placements without changing flags, and returns the permutation, mapping,
affected cells, and reread Key-to-Index facts. No name, image-similarity, usage-based,
or partial before/after ordering is inferred. This catalog entry remains a candidate
until a real Aseprite vertical slice proves lossless typed-Property movement and
save/close/reopen behavior.

### `export`

Owns delivery formats and their verified output facts. Export Operations read a
Sprite and produce Artifacts; they are not eligible Plan Steps. An animation export
that consumes a Tag declares its Playback Context and reports the expanded Frame
Number sequence, encoded timing, and output-format loop behavior. Export facts do not
rewrite the Tag's persisted `repeats`.

Every Export Operation uses explicit Export Destinations containing `path` and
`if_exists: fail | replace`; no command inherits Aseprite's overwrite prompt,
editor preferences, recent-file state, or an implicit overwrite. A fixed small
output set declares several Destinations directly. A generated multi-file command
whose cardinality follows bounded domain inputs declares an output directory and an
Aseprite-aligned Filename Format in its own schema. It resolves the complete expected
destination set and rejects empty expansion, collisions, duplicate paths,
unsupported placeholders, and disallowed existing files before invocation.

The fixed Lua Kernel owns native source selection, rendering, encoding, Filename
Format use, and all other core export semantics. The file adapter maps the declared
destinations into an operation-owned temporary output location, then verifies the
Kernel Response, every expected file, and the owning command's format-specific facts.
A zero exit or truthy Lua return alone is not success. Only validated files are
published and returned as the existing simple Artifact values.

This mechanism contains Aseprite's observed headless overwrite, false-success, and
metadata-before-texture behavior. It does not promise a filesystem transaction over
multiple final paths and does not introduce backups, rollback, an Artifact Manifest,
an artifact registry, or generalized recovery. A stronger publication guarantee must
be justified by the concrete multi-file vertical slice that needs it.

`spa export image` has a required discriminated Export Image Area: full `canvas`, an
explicit positive Canvas Pixel `bounds` Rectangle, or one exactly addressed `slice`
resolved to its effective Slice Key Bounds at the selected Frame. This is rectangular
source cropping. It accepts no canonical Selection Mask and never describes native
`SaveFileCopyAs.bounds` or editor Selected Canvas behavior as masked export. A real
1.3.18.5 probe preserved an unselected center pixel within Selection bounds. A future
true masked export remains valid product territory but must explicitly define
outside-mask transparency/fill, output bounds, Color Mode and Background behavior,
and verification through a separate evidence-bearing decision.

The Operation requires exactly one public one-based `frame_number` and one Layer
Composition. `visible` uses persisted effective hierarchy visibility with optional
exact exclusions; `all` renders every natively renderable Layer with optional exact
exclusions; `include` renders a non-empty set of exact Layer addresses. Group
inclusion/exclusion expands its descendant subtree, while an explicitly included
child enables the necessary ancestor Groups without adding unrelated descendants.
The Kernel applies and restores temporary visibility and reports the requested,
expanded, ancestor, excluded, and final native-stack-ordered Layer facts. It never
inherits active Frame/Layer, selected Range, `app.range`, names that are not unique,
or Layer globs. Aseprite owns compositing, Blend Mode, opacity, Background, Tilemap,
Reference, color, and pixel behavior. This command always returns one static raster
Artifact; Tags, Frame Ranges, playback, and multiple files belong to the animation
and sequence export commands.

The command reuses Aseprite's File Format rather than defining Static Image Format.
Its explicit `file_format` discriminated union must match the Export Destination
extension, with declared extension aliases, and each branch owns only that format's
native options. It uses the existing Color Mode vocabulary: `color_mode` has a
`preserve` request branch or a `change` branch containing one target Color Mode and
the accepted source/target-specific Change Color Mode inputs. Both this export branch
and `sprite change-color-mode` invoke the same fixed Kernel behavior; the export
branch applies it only to the disposable one-Frame Sprite.

For a change to Indexed, Palette preparation is an explicit export step before Change
Color Mode. The request either copies the selected source Frame's Effective Palette
to the disposable Sprite or applies the same fixed `palette color-quantization`
handler after Layer Composition has been rendered there. The latter naturally
quantizes that one rendered Frame. The result reports the chosen preparation and
complete resulting Palette. No branch silently quantizes, changes the Source Sprite,
or turns Palette preparation into part of Change Color Mode.

Transparency is likewise request structure rather than an Alpha Handling concept.
`transparency: preserve` forbids loss of required RGB/Grayscale Alpha Channel,
Indexed Transparent Color Index, or applicable Palette Entry transparency facts; an
alpha-less format remains valid when the actual selected result is proven opaque.
`transparency: background` requires one explicit fully opaque Background Color in the
effective export Color Mode and applies Aseprite Background semantics to the
disposable export Sprite. It never inherits editor color state.

`color_profile` is a separate required branch. `preserve` carries the source Color
Profile or its explicit absence to the disposable Sprite. `omit` applies native
Assign Color Profile with no profile and does not change pixels. `assign` applies an
explicit sRGB or ICC profile without changing pixels. `convert` applies native Convert
Color Profile to explicit sRGB or ICC before encoding. Assign and Convert never mutate
the Source Sprite. Each File Format branch declares whether it can encode no profile,
sRGB, or ICC; a requested profile it cannot represent fails instead of being omitted
or reduced to a different marker. The headless Kernel does not rely on
`app.preferences.color.manage`: a 1.3.18.5 probe observed the preference change but
produced byte-identical sRGB PNGs, while Assign None omitted the profile and
Assign/Convert ICC embedded it with different file digests.

The fixed internal execution order is:

1. render the requested Frame, Layer Composition, and Export Image Area into one
   disposable Sprite;
2. apply `color_profile`;
3. prepare the Palette when `color_mode.change` targets Indexed;
4. apply Change Color Mode;
5. apply `transparency`, interpreting Background Color in the final Color Mode and
   effective Color Profile; and
6. invoke the declared File Format encoder.

The public request cannot reorder, repeat, omit an applicable step, or expose
intermediate state. This sequence is not an Operation Plan, generic export pipeline,
stage plug-in surface, or source of intermediate Artifacts. The Python Application
Layer owns the accepted use-case orchestration and builds one private structured
execution; the Lua Kernel executes the selected packaged capabilities against the
same disposable Sprite in one Aseprite process.

The fixed Lua Kernel owns rendering, Change Color Mode, Assign/Convert Color Profile,
Background behavior, and native encoding; Python does not convert or composite pixels
or colors. Python can select, schedule, and compose those capabilities, validate ICC
inputs, and independently verify encoded profile facts; it cannot replace their core
semantics or silently change this accepted order. Results expose File Format/extension,
source and effective Color Mode, transparency/background decisions,
source/requested/effective/output Color Profile,
native options, and verified output. `spa info` reports stable proven support and does
not turn a runtime plug-in into a dynamic public schema branch.

| Candidate command | Intended meaning |
| --- | --- |
| `spa export image` | Export one explicit Frame and Layer Composition from the Canvas, explicit Bounds, or one effective Slice area as one static raster Artifact. |
| `spa export sheet` | Export sprite-sheet image and metadata Artifacts. |
| `spa export gif` | Export an animated GIF Artifact. |
| `spa export sequence` | Export a bounded sequence of frame image Artifacts. |
| `spa export tileset` | Export Tileset image and metadata Artifacts. |

Format conversion belongs here when its user-visible result is an exported file.
Conversion that changes the editable Sprite belongs to the native object whose
property changes; the catalog should not introduce a generic conversion subsystem.

### `plan`

Owns bounded composition of existing Sprite-bound read and mutation Operations. It
does not own alternate implementations of their behavior.

| Candidate command | Intended meaning |
| --- | --- |
| `spa plan check` | Validate plan shape, Operation eligibility, paths, Domain Bounds, and other statically decidable constraints. |
| `spa plan run` | Execute one bounded plan against one Sprite and commit at most one declared target. |

### `script`

Owns the explicit unrestricted escape hatch. Caller Scripts are not ordinary
Operations, cannot be Plan Steps, and do not establish supported SPA behavior.

| Candidate command | Intended meaning |
| --- | --- |
| `spa script run` | Execute an exact caller-owned Lua file or exact stdin bytes under the documented trust boundary. |

## Unresolved candidate groups

Some useful words do not yet justify a stable top-level group:

- `animation` may become an agent-facing composition group if workflows prove that
  cross-cutting operations over Frames, Cels, Tags, and timing have a cohesive
  language that is not adequately expressed by their native groups.
- text authoring needs a proven mapping to Aseprite's actual Sprite, Layer, Cel, and
  Image behavior before it receives either commands or a group.

These are explicit questions for dogfooding, not omissions to fill mechanically.
