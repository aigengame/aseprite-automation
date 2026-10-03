# Aseprite Automation

Aseprite Automation (SPA) provides agent-facing automation for Aseprite. `SPA` is the
short project name used in documentation; `spa` is the primary executable.

> [!IMPORTANT]
> This repository is at the bootstrap stage. Disposable prototypes tested selected feasibility assumptions; [issue #1](https://github.com/aigengame/aseprite-automation/issues/1) records their conclusions and is the umbrella product requirements document (PRD). The installed CLI provides runtime discovery, Sprite creation, inspection, copy, resize, crop, flatten, and validation, Layer addressing and mutation, Frame inspection, authoring, and editing, Cel inspection, lifecycle, placement, and native relationships, Tag inspection and authoring, Palette Change inspection and Entry edits, native Color Profile assignment and conversion, Cel-targeted Image resize, crop, canvas-resize, flip, and quarter-turn rotation, canonical Image reads and replacement, bounded Pixel Patch application, native Snapshot composition (`spa paint composite`), native Line, Rectangle, Ellipse, Contour, and Blur Paint operations, verified RGB PNG Image Export, animation audit, Frame comparison, and verified continuity Preview export. Feature issues own delivery contracts, evidence requirements, provenance links, curated evidence summaries, and status, while milestones group phase outcomes. [`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md) routes normative facts and document dependencies. The installed Surface Manifest reports shipped behavior.

For a complete authoring example, see [Moonlit Spell Practice](examples/wizard_cast/README.md):
a reproducible SPA wizard animation, reusable pixel assets, and a Godot target-practice demo.

This README owns the user-facing product introduction and promotion, value-proposition
narrative, onboarding, adoption guidance, and project navigation. Its factual claims
derive from the applicable product, architecture, delivery, and installed-runtime
authorities; it does not define a competing contract. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the integrated current system view.

## Background

Aseprite exposes useful batch and Lua scripting capabilities, but `aseprite --script` is not an agent-facing automation contract. A direct caller must still construct scripts, encode parameters, separate diagnostics from results, detect semantic failures, protect source files, and verify generated artifacts.

SPA adds that product boundary. It turns sprite workflows into parameterized Operations with typed inputs, structured results, stable failures, and observable postconditions. Ordinary Core Operations use packaged Lua handlers; they do not generate temporary Lua implementations. Caller-owned Lua remains the explicit `script run` escape hatch, but it cannot replace or bypass an existing Ordinary Core Operation through the SPA surface.

## Product Position

SPA is an **Aseprite automation toolchain for AI agents**. Its business capability is equivalent to Aseprite's: it provides agent-facing mechanisms for sprite creation, editing, inspection, validation, conversion, and export, and develops these functional capabilities broadly and deeply for agent use.

SPA provides a structured and verifiable loop:

```text
discover -> inspect when applicable -> create or edit
         -> inspect and validate -> continue editing or export
```

The product serves agents, continuous integration (CI) jobs, and asset pipelines that need explicit sprite operations and inspectable evidence. It preserves and observes native Aseprite behavior, including declared stochastic behavior. SPA does not take ownership of gameplay, engine integration, art direction, or another product domain.

## Capability coverage

The table introduces the product's intended capability coverage. Its rows are themes for
users, not Command Groups, Domain Modules, architecture ownership, or shipped-support
claims. A capability is supported after an evidence-bearing vertical slice ships and
appears in the installed Surface Manifest.

| Capability theme | Intended coverage |
| --- | --- |
| Runtime | Discover an external Aseprite installation, resources, version, scripting capabilities, and evidence-backed Capability Gaps. |
| Sprite and animation | Create and edit Sprites, Layers, Frames, Cels, Tags, timing, and animation structure. |
| Raster, paint, and selection | Inspect and transform Images; exchange bounded pixel data; apply Selections, native Paint operations, and native Filters. |
| Color and palette | Inspect and edit Palettes and color data; perform native quantization, Color Mode, Color Profile, and eligible Dithering operations. |
| Tile authoring | Create and inspect Tilemaps and Tilesets with stable Tile Keys, typed flags, explicit Coordinate Spaces, and bounded results. |
| Slices and imported content | Work with Slices, external raster input, and evidence-gated text rasterization through verified contracts. |
| Inspection and validation | Observe and validate each owned Aseprite concept beside its creation or editing capabilities. |
| Composition and delivery | Apply eligible Operations in a bounded single-Sprite Plan and export image, animation, sheet, Tileset, preview, and metadata Artifacts. |
| Agent access | Publish version-locked Agent Skill guidance and project the installed operation surface through the Model Context Protocol (MCP). |
| Asset workflow integration | Participate in external asset workflows through the public `spa` CLI JSON contract. |

Command Groups are navigation, not module architecture. Domain Modules own cohesive vertical slices and can project several groups when native behavior shares a lifecycle. `image` represents Aseprite Image observation and structural transformation; `paint` represents authoring intent. Native batch Filters remain distinct from native Tools. The [command catalog](docs/command-catalog.md) lists candidate territory; feature issues own delivery contracts.

## Public Contract

The CLI is the first Open Host Service. Its Published Language is the versioned
set of Operation Request, Operation Result, Failure Envelope, Operation metadata,
Artifact, and Surface Manifest schemas. Human output and MCP tools are projections of
the Published Language. The Python/Lua Kernel Protocol is a separate private contract,
not a second public API.

- Each Operation has strict typed request, result, and failure schemas.
- Machine output contains a schema-valid Operation Result or Failure Envelope and stays separate from vendor diagnostics.
- Stable Failure Codes drive automation; typed Failure Details and human Diagnostics have different roles.
- The Surface Manifest describes every callable Operation, side effects, determinism, version constraints, and schemas.
- Runtime-backed Operation Descriptors declare their Lua language, Aseprite API version, and native capability requirements. The Adapter verifies fixed probe prerequisites and reports runtime capabilities independently; the Application checks the selected Descriptor before Operation execution.
- Each Operation defines Aseprite-aligned target fields, cardinality, Inspection Scope, Operation Limits, and result facts. SPA has no universal Selector or Locator.
- Inspections report normalized coverage and completeness. Native absence, not requested, unsupported, and exceeded bounds remain distinct.
- Coordinate-bearing requests name their Coordinate Space. Public Rectangles use Aseprite's `x`, `y`, `width`, and `height` vocabulary and half-open coverage.
- Color Values preserve RGB, Grayscale, Indexed, Alpha Channel, Transparent Color Index, Palette, sRGB, and ICC distinctions from Aseprite.
- Supported multi-target Mutations resolve the complete target set and produce a Target Commit for the whole set or none of it.
- Every produced file is a verified Artifact in the owning Operation Result. Format-specific facts stay with that result.
- Operation Descriptors own registration and projections. The Lua Operation Kernel owns SPA Core Operation Semantics and native mapping. Python coordinates use cases and adapters without duplicating that behavior.
- Capability Gaps are versioned, evidence-backed runtime diagnostics, not proof of a separate native test on every selected Aseprite release. They make unavailable capabilities explicit instead of creating silent partial support.

Before delivery, exact feature contracts and evidence requirements belong to their
accepted issues under the shared language and decisions. Operation Descriptors own
implemented public contracts and bindings, implementation owns executable behavior,
tests and evidence artifacts own executed verification assertions and results, and the
installed Surface Manifest reports callable facts for one installation. See
[`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md).

## Technical Architecture

The accepted domain strategy separates **Sprite Authoring** (Core), **Asset
Preparation** (Supporting), and **Asset Delivery** (Supporting) within one context.
Reusable motion belongs to authoring; native save remains part of mutation completion.
Preparation contracts remain planned. Bounded Cel motion is available through
`motion apply`; Asset Delivery reuses existing exports. See [domain ownership](ARCHITECTURE.md#domain-ownership-view) and
[ADR-0095](docs/adr/0095-asset-preparation-authoring-and-delivery.md); the installed
Surface Manifest remains the source for callable capabilities.

SPA uses one **Sprite Automation** Bounded Context. Operation Descriptors project one
Published Language to the CLI, Agent Skill, MCP, and installed Surface Manifest.
Application use cases coordinate Domain Modules, an external Aseprite process, staged
file publication, and structured outcomes. Aseprite remains authoritative for native
behavior; packaged Lua handlers own SPA Core Operation Semantics and native mapping.
Application use cases coordinate the surrounding workflow without redefining that
native behavior.

The initial bootstrap stack, delivered by
[issue #3](https://github.com/aigengame/aseprite-automation/issues/3), is Python 3.13,
Typer, Pydantic 2, `uv`, a packaged Lua runtime probe, and an external
`aseprite --batch --script` runtime. Project metadata and the lockfile report the
actual dependencies. The operating model is a trusted
local workspace. Asset Pipeline integration uses a downstream-owned Anti-Corruption
Layer and the public `spa` CLI JSON contract.

## Try the installed CLI

For a source checkout, install Git LFS and run `git lfs install` followed by
`git lfs pull` before installing or building SPA. The packaged `.aseprite` probe
fixtures and example assets use LFS; the wheel needs their actual binary contents.

Install the project with `uv sync`, then point the runtime probe at an installed
Aseprite executable (on macOS, the binary inside `Aseprite.app/Contents/MacOS/`).
The commands emit JSON by default; `--human` renders the same outcome for reading.

```sh
uv run spa version
uv run spa info --aseprite /path/to/Aseprite.app/Contents/MacOS/aseprite
uv run spa schema --aseprite /path/to/Aseprite.app/Contents/MacOS/aseprite
uv run spa info --schema
uv run spa info --input-json '{"aseprite":"/path/to/Aseprite.app/Contents/MacOS/aseprite"}'
printf '%s\n' '{"aseprite":"/path/to/Aseprite.app/Contents/MacOS/aseprite"}' | uv run spa info --input-json -
uv run spa sprite create --input-json '{"aseprite":"/path/to/aseprite","target_sprite_file":"sprite.aseprite","width":16,"height":16,"color_mode":"rgb","initial_layer":{"kind":"transparent"},"overwrite":false}'
uv run spa sprite get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","inspection_scope":["frames","layers","cels"]}'
uv run spa sprite validate --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","expected":{"width":16,"height":16,"color_mode":"rgb","frame_count":1}}'
uv run spa sprite copy --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"copy.aseprite","overwrite":false}'
uv run spa sprite flatten --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"copy.aseprite","target_sprite_file":"flat.aseprite","in_place":false,"overwrite":false}'
uv run spa sprite resize --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"resized.aseprite","in_place":false,"overwrite":false,"width":32,"height":32}'
uv run spa sprite crop --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"cropped.aseprite","in_place":false,"overwrite":false,"coordinate_space":"canvas-pixel","rectangle":{"x":2,"y":2,"width":12,"height":12}}'
uv run spa frame list --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite"}'
uv run spa frame add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"timed.aseprite","in_place":false,"overwrite":false,"frame_number":2,"duration_ms":120}'
uv run spa frame duplicate --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"timed.aseprite","target_sprite_file":"duplicated.aseprite","in_place":false,"overwrite":false,"source_frame_number":1,"cel_mode":"copy"}'
uv run spa frame set --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"duplicated.aseprite","target_sprite_file":"retimed.aseprite","in_place":false,"overwrite":false,"frame_number":1,"duration_ms":150}'
uv run spa frame move --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"retimed.aseprite","target_sprite_file":"reordered.aseprite","in_place":false,"overwrite":false,"source_frame_number":1,"target_frame_number":3}'
uv run spa frame remove --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"reordered.aseprite","target_sprite_file":"trimmed.aseprite","in_place":false,"overwrite":false,"frame_number":2}'
uv run spa cel list --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","layer":{"layer_path":[1]},"from_frame":1,"to_frame":1}'
uv run spa cel get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","target":{"layer":{"layer_path":[1]},"frame_number":1}}'
uv run spa cel add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"timed.aseprite","target_sprite_file":"with-cel.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":2}}'
uv run spa cel clear --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"with-cel.aseprite","target_sprite_file":"cleared.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":2}}'
uv run spa cel remove --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"cleared.aseprite","target_sprite_file":"without-cel.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":2}}'
uv run spa image resize --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"resized-image.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"width":32,"height":32,"method":"nearest-neighbor","position_policy":{"kind":"keep"}}'
uv run spa image get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","source":{"kind":"individual","target":{"layer":{"layer_path":[1]},"frame_number":1},"rectangle":{"x":0,"y":0,"width":16,"height":16}},"snapshot_destination":{"path":"pixels.json","if_exists":"fail"}}'
uv run spa image get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","source":{"kind":"composite","output_color_mode":"rgb","frame_number":1,"rectangle":{"x":0,"y":0,"width":16,"height":16},"layer_composition":{"mode":"visible"}}}'
uv run spa image replace --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"replaced.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"input":{"kind":"artifact","path":"pixels.json"}}'
uv run spa image flip --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"flipped.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"axis":"horizontal"}'
uv run spa image rotate --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"rotated.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"angle":90,"position_policy":{"kind":"pivot","pivot_x":1,"pivot_y":0}}'
uv run spa layer list --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite"}'
uv run spa layer get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","target":{"layer_path":[1]}}'
uv run spa layer add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"layered.aseprite","in_place":false,"overwrite":false,"kind":"group","name":"effects"}'
uv run spa layer set --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"named.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1]},"properties":{"name":"background-art","is_visible":true}}'
uv run spa layer move --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"moved.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]},"stack_index":1}'
uv run spa layer remove --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"removed.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]}}'
uv run spa layer add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"two-image-layers.aseprite","in_place":false,"overwrite":false,"kind":"transparent","name":"upper"}'
uv run spa layer merge --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"two-image-layers.aseprite","target_sprite_file":"merged.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]}}'
uv run spa layer convert-to-background --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"background.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1]},"background_color":{"kind":"rgba","red":10,"green":20,"blue":30,"alpha":255}}'
uv run spa layer convert-from-background --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"background.aseprite","target_sprite_file":"transparent.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1]}}'
uv run spa paint apply --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"painted.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1],"frame_number":1},"patch":{"coordinate_space":"image-pixel","rectangle":{"x":0,"y":0,"width":2,"height":1},"runs":[{"x":0,"y":0,"length":2,"color":{"kind":"rgba","red":255,"green":0,"blue":0,"alpha":255}}]}}'
uv run spa plan check --input-json '{"plan":{"source_sprite_file":"sprite.aseprite","steps":[{"operation":"sprite get","input":{"inspection_scope":["frames","layers"]}}]}}'
uv run spa plan run --input-json '{"aseprite":"/path/to/aseprite","plan":{"source_sprite_file":"sprite.aseprite","steps":[{"operation":"sprite get","input":{"inspection_scope":["frames","layers"]}}]}}'
uv run spa export image --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","destination":{"path":"image.png","if_exists":"fail"},"frame_number":1,"color_mode":"preserve","color_profile":"preserve","transparency":"preserve"}'
```

`--input-json -` reads one complete JSON request object from stdin; a literal
`--input-json` value remains available for short invocations.
`spa sprite create` requires an explicit `overwrite` boolean and refuses to replace an
existing Target Sprite File when it is `false`.
`spa sprite validate` requires at least one expected width, height, Color Mode, or
Frame count. It lists only those checks with their actual values; a mismatch returns
a typed Finding in a successful read result.
`spa sprite copy` preserves the Source Sprite File byte for byte, including native
Tile content, and reopens the staged copy before Target Commit. Source and Target must
be distinct publication entries. A Source read or staging I/O failure reports
`sprite_copy_staging_failed` without a Target Commit.
`spa sprite flatten` uses native Aseprite flattening. Its result gives complete
`before_sprite` and reopened `sprite` inspections so callers can see the effects on
Layers, Cels, Color Mode, Palettes, Tags, and Slices. Native flattening includes
pixels from hidden Layers, so the flattened image can differ from the Source's
visible composite. This slice rejects a Sprite with
any Tileset or Tilemap Layer before mutation and reports
`sprite_flatten_unsupported_content` without a Target Commit. In-place flattening
requires `in_place: true` and `overwrite: true`.
`spa sprite resize` uses Aseprite's nearest-neighbor resize at Canvas origin `(0, 0)`
with explicit positive dimensions. `spa sprite crop` requires a non-empty, half-open
Canvas Pixel Rectangle wholly within the current canvas and trims outside Cel
content. Both operations reject a Sprite containing any Tileset, Tilemap Layer,
Tilemap Cel, or Tilemap Image before native mutation and Target Commit. Their
results include before and reopened Sprite inspections, old and new canvas sizes,
and observed Cel bounds, Tags, Slices, and Grid. Crop also reports `clipped_cels`
with each affected Cel's bounds before and after clipping; these are geometry facts,
not a count of colored pixels. Aseprite moves Reference Layer Cels without trimming
their images, so they do not appear in `clipped_cels`. In-place edits require
`in_place: true` and `overwrite: true`.
`spa layer list` returns the current hierarchy. `spa layer get` accepts one
`layer_path`, `layer_uuid`, or `layer_name`. Paths use one-based native sibling
positions. Names use exact case-sensitive matching and must be unique across the
Sprite. UUIDs are returned only when verified across independent opens of the saved
Sprite; a Layer with no verified saved UUID reports `null`. SPA preserves the
Sprite's existing `useLayerUuids` value.
`spa layer add` creates a regular Transparent or Group Layer at the root, or as
the last child of the Group selected by `parent`. Its result reports the Layer's
address after save and reopen. These Layer commands are not Plan Steps.
`spa layer set` changes name, visibility, and editability on a regular Transparent
Image or Group Layer; opacity and blend mode require a regular Transparent Image.
`spa layer move` changes only the sibling stack position under the current parent.
`spa layer remove` deletes one addressed subtree but rejects Tilemap content.
`spa layer merge` merges a regular Transparent Image into its immediate lower
regular Transparent Image sibling. It sets Aseprite's experimental
`new_blend=true` preference during native Merge Down and restores its previous
value. All four return
before/after Layer and Cel facts, directly affected object addresses, rendered
Frame digests, and save/reopen verification before Target Commit. They are
standalone mutations and are not Plan Steps. An operation that changes no Layer
or Cel facts reports empty affected sets; Group visibility and editability
changes include descendants whose effective state changes.
`spa layer convert-to-background` requires a visible, editable regular
Transparent Image Layer, no existing Background, and an explicit opaque Color
Value compatible with the Sprite Color Mode and, for Indexed Sprites, the
Effective Palette at every Frame. Aseprite moves the converted Layer to the
root bottom, names it `Background`, fills transparent pixels, and ensures an
opaque, full-canvas Cel on every Frame.
`spa layer convert-from-background` requires a visible, editable Background
Layer and preserves its Cel images while accepting Aseprite's resulting Layer
name. Both results report the before/after Layer facts, complete affected Frame
numbers, created Cel count, and per-Frame before/after Cel facts. These are
standalone mutations and are not Plan Steps.
`spa paint apply` accepts at most 256 addressed Image Pixels per request. It defaults
to rejecting out-of-bounds pixels; `clipping: "clip"` is the explicit clipping policy.
In-place editing requires Source and Target to name the same publication entry,
plus both `in_place: true` and `overwrite: true`.
Standalone Paint rejects a Source alias that traverses the Target publication entry
for either `in_place` value.

`spa paint composite` blends a canonical Pixel Region Snapshot into one existing
regular Cel through native `Image:drawImage`. Supply the Snapshot as
`input: {"kind":"inline","snapshot":...}` (up to 4096 pixels) or the identical
JSON in `input: {"kind":"artifact","path":"snapshot.json"}`. Source and target
Color Modes must match. `position` places the rebased source origin in the target
Image's pixel coordinates. Both position coordinates must be signed 32-bit integers
(`-2147483648..2147483647`); out-of-range values fail before native invocation.
`opacity` is an explicit integer in `0..255`, and
`blend_mode` is explicit. Clipping and Selection follow `paint apply`; omitted
Selection is unrestricted. A shared Image is composited once, preserving all Linked
Cels. The result reports applied/skipped coverage, changed stored pixels, digests,
and every affected Cel after save/reopen verification. Pixels included by coverage
can be unchanged; native alpha-zero RGB values are not normalized by SPA.

The verified Aseprite 1.3.18.5 baseline supports all 19 published modes for RGB.
Grayscale excludes `hue`, `saturation`, `color`, `luminosity`, and `addition`:
those native combinations select Normal or Exclusion instead. Indexed accepts only
`normal` at `opacity: 255`, using native index overlay with the Sprite's Transparent
Color Index. Supply `palette_frame_number` equal to `target.frame_number`; the result
reports that Frame's Effective Palette. An isolated temporary Sprite provides the
correct native Palette basis. Source indexes and the mask must exist in that Palette;
output indexes must exist in every affected Cel Frame's Palette. Other Indexed
combinations return typed Capability Gaps. `spa info` and `spa schema` expose these
gaps and omit the Indexed capability if its native probe fails. Composite is a
standalone mutation; it is not an Operation Plan Step.
These exclusions are the delivered SPA support boundary based on the 1.3.18.5
evidence, not a claim of separate mode-matrix tests on every Aseprite release.

```sh
uv run spa paint composite --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"composited.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"input":{"kind":"artifact","path":"snapshot.json"},"position":{"x":0,"y":0},"opacity":127,"blend_mode":"normal"}'
```

`spa paint contour` accepts a non-empty `points` array in Image Pixel space and
`freehand_algorithm: "regular"` or `"pixel-perfect"`. Points form one native
gesture; their order and multiplicity are preserved. Native Contour owns closure
and fill. The Brush, Color Value, Ink, opacity, clipping, Selection Application,
and publication rules below also apply.

`spa paint blur` takes the same ordered gesture, Standard Paint Brush, opacity,
and Freehand Algorithm, plus required `tiled_mode: none | x | y | both`. It uses
fixed native Blur Ink, accepts no Color Value or caller-selected Ink, and retains
the requested opacity. Native Blur performs its neighborhood sampling on the
original document. Tiled Mode wraps at the Sprite boundary; its reported coverage
includes wrapped pixels and follows native clipping on the other axis. Image
bounds and Selection Application still restrict publication. Indexed results
include the Effective Palette facts for the affected Frames.

`spa paint gradient` is absent from the callable Surface Manifest. On Aseprite
1.3.18.5, Gradient Type and Dithering Matrix depend on the GUI Context Bar and
cannot be supplied through a faithful headless `app.useTool` route. `spa info`
and `spa schema` report this version-specific Capability Gap. Other runtimes stay
unverified until a complete route passes the gate in [#28](https://github.com/aigengame/aseprite-automation/issues/28).
Contour Paint Dynamics, pressure, velocity, and tilt are also reported as a
Capability Gap and are outside its request schema.

`spa paint fill`, `spa paint pencil`, `spa paint eraser`, `spa paint line`,
`spa paint rectangle`, and `spa paint ellipse` use native
Aseprite Tools on an existing Cel addressed by `target.layer` and
`target.frame_number`. Geometry uses `coordinate_space: image-pixel`. Line takes
exactly `from` and `to`; equal Points keep native single-point behavior. Shapes
share positive half-open `bounds` and explicit `style: outline | filled`.
Dimensions of 1 retain the selected native shape's output.

A Standard Paint Brush has `kind: circle | square | line` and positive `size`.
Circle fixes its angle to 0 and rejects an angle field; square and line require
an integer `angle` in `-180..180`. A line Brush is an oriented footprint, distinct
from the Line Tool. A Color Value must match the Sprite's Color Mode.
`opacity` is required in `0..255`. For operations with an Ink input, native
`simple` and `copy-color` use effective
opacity 255 at every valid requested opacity; `alpha-compositing` and `lock-alpha`
use the requested value. Results report both. This does not change the Color
Value's alpha. `shading` returns a typed `paint_capability_gap` until an explicit
Shade contract is available; Image Brushes are outside this request schema.

Clipping is evaluated against native coverage, which can extend beyond the target
Image. `clipping: reject` refuses coverage
outside the Image; `clip` reports and excludes it. Optional Selection Application
then filters the remaining pixels by their Canvas Pixel positions. Results separate
requested, applied, clipped, and Selection-excluded coverage, changed pixels, affected Cels,
and before/after digests. Native tool preferences are isolated and restored.
Drawing preserves Image size, Cel position, linked sharing, and opaque Background
postconditions; it never creates a Cel or implicitly expands an Image. Each
Operation has an independent runtime capability probe and a fixed packaged handler.
These native Paint Operations are standalone mutations, not Plan Steps.

```sh
uv run spa paint line --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"line.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"coordinate_space":"image-pixel","from":{"x":2,"y":2},"to":{"x":10,"y":2},"brush":{"kind":"circle","size":1},"color":{"kind":"rgba","red":255,"green":0,"blue":0,"alpha":255},"ink":"simple","opacity":255}'
```

Pencil and Eraser take one non-empty ordered `points` sequence and an explicit
`freehand_algorithm: regular | pixel-perfect | dots`. A single Point is valid.
The sequence is one native gesture; SPA preserves order and repeated Points.
Each algorithm is admitted separately by a native probe. Image Brush, shading
Ink, and Paint Dynamics remain reported Capability Gaps.

Eraser takes `behavior` instead of Color and Ink. `{"kind":"erase"}` erases alpha
on RGB/Grayscale Transparent Layers or writes the Transparent Color Index on
Indexed Layers. Background erase requires `background_color` in that behavior;
Transparent Layer erase forbids it. `kind: replace-foreground-with-background`
requires both `foreground_color` and `background_color` and uses native matching
replacement. Eraser retains its own native opacity behavior; its effective opacity
is the requested value. No public mouse button or generic Ink is accepted.

Fill takes one `seed` and no Brush. It requires `tolerance: 0..255`, `contiguous`,
`refer_to: active-layer | all-layers`, and boolean `stop_at_grid`. A contiguous
Fill also requires `connectivity: four-connected | eight-connected`; a
non-contiguous Fill omits connectivity. `all-layers` matches the native visible
composite at the addressed Frame and still writes only the target Cel.
Grid stopping uses the saved Sprite Grid cell containing the seed; it does not
depend on GUI grid visibility. Results report the matching source and effective
Grid cell in Canvas Pixel coordinates.

Fill matching is bounded by the original Sprite Canvas. Its Image Pixel seed is
mapped through the target Cel position and must be inside that Canvas. Image
clipping and optional Selection then filter the matched pixels for writing.
Selection does not limit flood traversal: if only the two endpoints of five
connected same-color pixels are selected, filling from the first endpoint writes
both endpoints. These current policies follow [issue #27](https://github.com/aigengame/aseprite-automation/issues/27);
future requirements can add explicit alternatives. See the
[native validation evidence](docs/evidence/issue-27-native-paint.md).

`spa filter brightness-contrast` runs Aseprite's native Filter with required integer
`brightness` and `contrast` in `-100..100`. Explicit `0`/`0` reports a no-op.
For example, adjust Red on an RGB Image Layer:

```sh
spa filter brightness-contrast --input-json '{
  "source_sprite_file":"source.aseprite",
  "target_sprite_file":"adjusted.aseprite",
  "in_place":false,"overwrite":false,
  "brightness":20,"contrast":0,
  "application":{
    "kind":"pixels","color_mode":"rgb",
    "channels":{"kind":"components","names":["red"]},
    "cels_target":{"kind":"selected","layers":[{"layer_path":[1]}],"frame_numbers":[1]}
  }
}'
```

Use `spa filter brightness-contrast --schema` for the installed request and result
contracts. Applications are:

| Application | Color Mode | Palette and target inputs |
| --- | --- | --- |
| `pixels` | `rgb`, `grayscale`, `indexed` | `cels_target`; Indexed also requires `palette_frame_number` as the Effective Palette/RGB Map basis. |
| `indexed-palette-entries` | Indexed | Exact Palette Change at `palette_frame_number`; `entries: {"kind":"all"}` or `{"kind":"selected","indexes":[1]}`. No Cel target or Selection. |
| `rgb-palette-colors` | RGB | Exact Palette Change, `indexes`, and `cels_target`; adjusts selected Entries and applies native exact-color lookup to participating pixels. |

For `rgb-palette-colors`, Aseprite finds the first Palette Entry (lowest Palette
Index) whose old RGBA exactly matches each participating pixel, then reads the
color at that Index from the adjusted Palette. If Entries have duplicate RGBA values,
selecting only a later Entry can change that Entry while leaving matching pixels
unchanged.

Channels are a non-empty unique subset of `red`, `green`, `blue`, or only `gray`
for Grayscale. Alpha and stored Index adjustment are unsupported. RGB/Grayscale
pixel Alpha and Palette Entry Alpha are preserved; Indexed pixel RGB Map
quantization may choose an Entry with different Alpha.

`cels_target` is either the explicit Layer/Frame Cartesian product above or
`{"kind":"all"}` for every editable existing Cel. Missing intersections are
reported without creating Cels. Explicit non-editable Layers reject the operation;
`all` reports exclusions. Shared Linked Cel Images are filtered once, and results
include affected Cels outside the selected range. Pixel applications optionally take
an explicit Canvas Pixel `selection`; omission selects the whole Canvas, while
`{"kind":"empty"}` selects no pixels. Empty Selection still allows the Palette
part of `rgb-palette-colors` to change.

Brightness/Contrast accepts resolved Tilemap pixel targets with explicit
`tileset_mode: "manual"` on the pixel application and a verified runtime capability.
It checks the native Site mode before mutation; omitted Manual intent or a different
observed mode rejects the whole request. Ordinary Image targets and Indexed
Palette-only applications do not require that Tilemap capability. Tilemap placement
Images, flags, Tileset bindings, Grid, topology, and metadata stay unchanged.
`changed_tiles` reports changed Tile bitmaps and referencing Cels, including references
outside the requested range or Selection. Native shared-Tile effects can occur more
than once across distinct target Cel Images; this is not a once-per-Tile contract.

Indexed Palette-only application can use a private Tilemap-only anchor and verifies
that ordinary Images, Tilemap placement Images, and all Tile Images remain unchanged.
A Palette basis Frame without a usable anchor produces `filter_unsupported_document`.
These are the delivery boundaries of
[issue #35](https://github.com/aigengame/aseprite-automation/issues/35) and
[issue #152](https://github.com/aigengame/aseprite-automation/issues/152).
Installed discovery reports the selected runtime's Manual Tilemap Capability Gap
when that native probe does not pass. Hue/Saturation retains its separate boundary below.

Results include effective Selection, Channels, Palette basis and indexes,
requested intersections, existing targets, exclusions, unique Image observations,
processed Image numbers, affected Cels, and the verified Target Commit. Filter
capability checks are independent of native Paint checks.

`spa filter hue-saturation` uses the same five Filter Applications, targets,
Selection, and Palette basis rules. Its Channels add `alpha` to RGB/Indexed or
Grayscale components; stored `index` is invalid. Each selected Channel requires
exactly its applicable parameters:

| Selected Channels | Required parameters |
| --- | --- |
| Any of `red`, `green`, `blue` | `adjustment` with `mode: hsl-multiply` or `hsl-add`, integer `hue: -180..180`, `saturation: -100..100`, `lightness: -100..100`; alternatively `hsv-multiply` or `hsv-add` with `value` instead of `lightness`. |
| `gray` | `adjustment: {"mode":"grayscale","lightness":-100..100}`; no Hue/Saturation choice. |
| `alpha` | Independent integer `alpha: -100..100`. |

Omit `adjustment` for Alpha-only requests and omit `alpha` when that Channel is
not selected. All governed values may be zero: an all-zero request skips native
writeback and reports a no-op, preserving existing bounds and duplicate Indexed
Entries. For example, rotate Hue and fade selected RGB Cels:

```sh
spa filter hue-saturation --input-json '{
  "source_sprite_file":"source.aseprite",
  "target_sprite_file":"adjusted.aseprite",
  "in_place":false,"overwrite":false,
  "adjustment":{"mode":"hsl-add","hue":30,"saturation":0,"lightness":0},
  "alpha":-25,
  "application":{
    "kind":"pixels","color_mode":"rgb",
    "channels":{"kind":"components","names":["red","green","blue","alpha"]},
    "cels_target":{"kind":"selected","layers":[{"layer_path":[1]}],"frame_numbers":[1]}
  }
}'
```

Aseprite owns adjustment, clamping, and quantization; zero Alpha stays transparent
at the adjustment stage. Indexed pixels still resolve through the declared RGB Map,
so their final RGBA belongs to the selected Palette Entry. Background pixel targets
reject Alpha requests, including zero, instead of silently ignoring the Channel.
Palette-mutating Alpha also needs a non-Background execution anchor at the
Palette basis Frame, including for zero Alpha. SPA chooses an available suitable
anchor; otherwise it reports `filter_unsupported_document`. This current boundary
avoids Aseprite silently removing the Alpha flag and can be extended when a future
requirement and native evidence justify another execution path.
Tilemap pixel targets are outside the current #36 delivery and reject the whole
operation; Palette-only can use a non-mutating Tilemap anchor. These current
boundaries can be extended by later feature requirements.

Native writeback may trim transparent borders or delete fully transparent Cels,
including linked Cels outside the requested range. Hue/Saturation results add
`cel_effects` with each affected Cel's before/after Canvas bounds (`after: null`
means native deletion); an Image deleted with its Cels has
`after_content_digest: null`. Live and saved/reopened state must agree before
Target Commit. Use `spa filter hue-saturation --schema` for the full contract;
its independent runtime gate verifies all four HSL/HSV modes through the packaged
native command path. See [#36 native evidence](docs/evidence/issue-36-hue-saturation.md).

`spa filter invert-color` and `spa filter outline` operate on ordinary Image Layer
Cels. They require explicit `color_mode`, `channels`, and `cels_target`, accept
optional pixel `selection`, and have no `application` field. Each call publishes
its own Target Commit; neither is an Operation Plan Step.

```bash
spa filter invert-color --input-json '{
  "source_sprite_file": "input.aseprite",
  "target_sprite_file": "inverted.aseprite",
  "in_place": false, "overwrite": false,
  "color_mode": "rgb",
  "channels": {"kind": "components", "names": ["red", "green", "blue"]},
  "cels_target": {"kind": "all"}
}'
```

RGB Channels are `red`, `green`, `blue`, and `alpha`; Grayscale Channels are
`gray` and `alpha`. Indexed Invert Color requires `palette_frame_number` and
either RGBA `components` or exclusive `{"kind":"index"}`. Index execution uses
native `255 - index`. Before invocation, every selected Canvas input and result
Index must exist in the declared Effective Palette, including index-zero padding
outside Cel bounds. `filter_index_out_of_bounds` reports the Palette basis,
source/result Indexes, Layer paths, Frame numbers, and Canvas Pixel positions.
SPA does not expand the Palette or switch interpretation. Indexed component
quantization does not promise exact two-pass restoration.

Outline additionally requires `place` (`inside`/`outside`), compatible
`outline_color` and `background_color` Color Values, `tiled_mode`
(`none`/`x`/`y`/`both`), and `matrix`. Matrix is either
`{"kind":"preset","name":"circle"}` (`none`, `square`, `horizontal`, and
`vertical` are also valid), or `{"kind":"custom","neighbors":["top-left","left"]}`.
Custom neighbors name the sampled pixels relative to a candidate; a top-left
neighbor can create an outline pixel below and right of the source. The eight
neighbors exclude the center; empty or repeated custom entries are invalid.
`none` requests the native empty neighborhood.

Selection limits Outline writes; neighborhood reads can cross its boundary.
Non-tiled edges use native clamping; tiled axes wrap at Canvas edges. RGB/Gray
mixed targets use a selected non-Background color anchor; Background-only targets
retain native opaque color projection. Indexed Outline requires valid Palette
Index Color Values and exclusive Index Channels. Indexed component Outline is
reported as a Capability Gap based on Aseprite 1.3.18.5 evidence.

Both operations refuse any resolved Tilemap target and Background Alpha before
mutation, including `all` and mixed requests. Ordinary targets in documents with
unrelated Tilemaps remain usable. Results preserve Palette facts and report native
Image changes, linked Cel effects, bounds or deletion, and verified save/reopen
observations. Use each command's `--schema` for its installed contract. See
[#38 native evidence](docs/evidence/issue-38-invert-outline.md).

`spa filter despeckle` applies the native Median Filter to ordinary Image Layers.
Required `width` and `height` are integers in `1..100`, including even sizes;
`tiled_mode` is `none`, `x`, `y`, or `both`. The request uses `pixels` with explicit
Color Mode, Channels, Cel targets, and optional Selection. It has no `application`
field and does not edit Palette Entries. For example:

```sh
spa filter despeckle --input-json '{
  "source_sprite_file": "source.aseprite",
  "target_sprite_file": "smoothed.aseprite",
  "in_place": false,
  "overwrite": false,
  "width": 3,
  "height": 3,
  "tiled_mode": "none",
  "pixels": {
    "color_mode": "rgb",
    "channels": {"kind": "components", "names": ["red", "green", "blue"]},
    "cels_target": {"kind": "all"}
  }
}'
```

RGB accepts nonempty RGBA subsets; Grayscale accepts Gray/Alpha subsets. Indexed
requires `palette_frame_number` and either `channels: {"kind":"index"}` or
component Channels that include Green. Native 1.3.18.5 corrupts preserved Green
in the other component sets; this slice refuses them instead of adding Channels.
Resolved Tilemap pixels and Background Alpha also refuse before mutation. These
current boundaries can be extended by accepted requirements and native evidence.
Results report the native window anchor, sample count, actual changed Images and
Cel bounds, and verified save/reopen. A 1×1 window still invokes Aseprite: Indexed
component processing can remap duplicate Palette colors to a different stored
Index. Edge sampling follows Aseprite: `none` disables wrapping, but native
1.3.18.5 can deviate from ideal edge repetition for wide windows; SPA preserves
that observed output instead of repairing the native algorithm. See [#39 native evidence](docs/evidence/issue-39-native-filters.md).

Convolution Matrix has no callable Descriptor. `spa info` and `spa schema` expose
`runtime.convolution`: bounded Resource declarations, source paths, duplicate
names, declared default Channels, scan completeness/notes, and requested versus
observed native probe pixels. These are discovery facts, not proof that each
Resource is usable. Coefficients, divisor, and bias remain opaque. On the current
native baseline, Red and Alpha requests change the same RGBA components and an
unknown Resource succeeds as a no-op. The Surface Manifest reports this Capability
Gap. A later runtime still needs the full #39 acceptance gate before a callable
Convolution Operation can be delivered.

`spa selection create/combine/invert/grow/shrink/transform` return explicit
Canvas Pixel values. Requests declare `coordinate_space: "canvas-pixel"`; values
can be inline (`empty`, rectangular `all`, or canonical `mask`) or read from a
`{"kind":"artifact","path":"mask.json"}` input. Pass a result's `selection` to
Paint explicitly. Omitting Paint's Selection remains unrestricted; `empty`
selects no pixels.

Create accepts `shape.kind` of `rectangle`, `ellipse`, or `mask`. Combine accepts
`union`, `intersect`, `subtract`, and `xor`. Invert and morphology require a
positive `canvas` Rectangle. Grow/shrink require an explicit positive `radius`
and `shape: "circle" | "square"`; grow clips to that Canvas, while input coverage
outside it is rejected.

Transform requires `canvas` and one of `translate` (integer `offset`), `flip`
(`axis`), `rotate` (`angle: 90 | -90 | 180`), or `scale` (positive `width/height`).
Scale uses native nearest-neighbor sampling. Flip/rotate/scale retain the source
tight bounds' left/top. `target_placement` reports the requested placement;
`bounds` and `pixel_count` describe actual selected coverage, which can shrink or
vanish during scaling. A transform refuses out-of-canvas selected pixels.
The native adapter also refuses lossy integer conversion or a native temporary
Canvas that differs from the request; it cannot report wrapped coordinates as success.

`spa selection validate` returns encoding, Coordinate Space, and optional Canvas
containment Findings without repairing the input. `selection export` stages and
verifies canonical JSON. `selection preview` requires an explicit Canvas and
stages and independently decodes a PNG: selected pixels are opaque white,
unselected pixels transparent black. That image is derived evidence. Both use
`destination: {"path": "...", "if_exists": "fail" | "replace"}` and publish only
after verification; input Artifact aliases cannot be overwritten.

```sh
uv run spa selection create --input-json '{"aseprite":"/path/to/aseprite","coordinate_space":"canvas-pixel","shape":{"kind":"ellipse","bounds":{"x":10,"y":20,"width":4,"height":4}}}'
uv run spa selection transform --input-json '{"aseprite":"/path/to/aseprite","coordinate_space":"canvas-pixel","selection":{"kind":"all","rectangle":{"x":10,"y":20,"width":2,"height":1}},"canvas":{"x":0,"y":0,"width":32,"height":32},"transform":{"kind":"rotate","angle":90}}'
```

`spa frame add` inserts an empty Frame at a one-based position with an explicit
`duration_ms` (1–65535). A Sprite with a Background Layer also requires a compatible
`background_color`; other new Layer/Frame intersections remain absent.
`spa frame duplicate` inserts immediately after its source Frame. It preserves the
source duration unless overridden and requires `cel_mode: "copy"` or `"link"`.
Both operations report native Tag Range adjustments and verify the staged Sprite
after reopening it.
The result also reports the effective Background fill or each duplicated Cel's
Layer path and copy/link relationship.
`spa frame set` changes one Frame's duration. `spa frame move` places one Frame at
its one-based final Frame Number; moving Frame 1 to Frame 3 in `[A, B, C, D]`
produces `[B, C, A, D]`. `spa frame remove` deletes one Frame but refuses to
remove the Sprite's final Frame. These standalone mutations report observed native
changes to Frame numbers, Cels, Tag ranges, Slice Keys, and Palette Changes when
present, and verify the staged Sprite after reopening it before Target Commit.

`spa cel list` inspects an inclusive Frame Range on one exactly addressed Layer;
`spa cel get` inspects one Layer/Frame intersection. Both report absence separately
from an existing transparent Image. Existing Cel facts include position, Image
bounds, opacity, z-index, and other native Cels sharing the Image. `cel add`
creates an independent transparent Image at an absent regular Transparent
Layer intersection. Optional `image_size: {"width": 24, "height": 32}` sets its
initial dimensions; omit it or pass `null` for the Sprite Canvas size. Both
dimensions must be integers from 1 through 65535. An Image may exceed the Canvas
without resizing it. Creation uses the Sprite's Color Mode, Color Profile, and
Transparent Color Index, with position `(0, 0)`, opacity 255, and z-index 0.
The same option is available in a `cel add` Plan Step, including before a Paint
Step; returned dimensions remain in `cel.image_bounds`.
`cel clear` and `cel remove` do not accept `image_size`.
`cel clear` preserves the Cel and its Image bounds; on a
Background Layer it requires an explicit compatible `background_color` and fills
the Cel with that color. Clearing a shared Image preserves native links and reports
every affected Cel in `affected_cels`. `cel remove` makes a regular Transparent Cel
absent and rejects Background Cels. Mutations verify the staged Sprite after reopening it.
`cel set` changes position, opacity, or z-index without replacing pixels. `cel copy`
creates an independent Image at an absent destination; `cel link` shares the Image,
position, and opacity with an absent Frame on the same Layer. Z-index remains
individual to each Cel. `cel unlink` makes one Linked Cel independent while
retaining its pixels. It refuses a locked target Layer or locked ancestor.
`before_cels` records the validated input scope; `affected_cels` reports the
Cel targets of the mutation after reopening the staged Sprite.
Paint requires an existing Cel and Image and reports `cel_not_found` when absent.
Tilemap Cel inspection reports existence and Canvas Pixel position with
`image_bounds: null`; Tile Cell geometry belongs to Tilemap inspection.

`spa motion apply` authors position offsets, absolute opacity, or both over an
inclusive `from_frame`/`to_frame` range on one exact `layer`. Every target Cel
must already exist on a regular Transparent Layer. RGB, Grayscale, and Indexed
are supported, including hidden and locked Layers. A target sharing its Image
with any other Cel is refused; explicitly unlink it first when appropriate.
Images, stored pixels, z-index, Frame durations, and unrelated facts are preserved.

Each curve requires ordered unique keys at both range endpoints (one key for a
single Frame), its own `interpolation` (`step`, `linear`, or `smoothstep`), and its
own `rounding` (`toward-zero`, `floor`, `ceil`, or `nearest-away-from-zero`).
Sampling uses Frame Number, not duration. Step interpolation holds the left key
until the next key's Frame. Smoothstep uses `3t² - 2t³`. Position offsets are
rounded before addition to each Cel's own starting position; they accept ±65535,
while resulting positions must fit signed 16-bit coordinates. Movement outside
the canvas is permitted. Opacity is absolute, from 0 through 255. Omitted curves
preserve their property. The timeline and unique in-range keys bound the work;
there is no 64-Cel limit.

```sh
spa motion apply --input-json '{
  "source_sprite_file": "poses.aseprite",
  "target_sprite_file": "moved.aseprite",
  "in_place": false, "overwrite": false,
  "layer": {"layer_path": [1]}, "from_frame": 1, "to_frame": 5,
  "position_offsets": {
    "interpolation": "smoothstep", "rounding": "nearest-away-from-zero",
    "keys": [
      {"frame_number": 1, "offset": {"x": 0, "y": 0}},
      {"frame_number": 5, "offset": {"x": 8, "y": -4}}
    ]
  }
}'
```

Motion validates every target and sampled result before mutation. Its `cels`
result records each Cel's `before`, `after`, and sampled `offset`, and the
standalone operation verifies save/reopen before Target Commit. The same frozen
input and request reproduce native facts and pixels; applying relative motion to
an already moved input accumulates displacement. Numeric verification does not
establish visual continuity or artistic quality.

`spa image resize` targets an existing Image on a regular Transparent Cel.
It requires positive dimensions, `nearest-neighbor`, `bilinear`, or `rotsprite`,
and a `keep` or `pivot` Cel-position policy. `pivot` requires signed 32-bit
integer `pivot_x`/`pivot_y` in old Image Pixel space (including points outside
the Image bounds) and an explicit rounding mode:
`toward-zero`, `floor`, `ceil`, or `nearest-away-from-zero`. Indexed `bilinear`
also requires `palette_frame_number` to select the Effective Palette; other
Color Modes and methods reject that input. The operation transforms a source
copy, preserves every native Cel link to the Image, applies one rounded offset
to each affected Cel, and verifies the staged Sprite after save/reopen.

`spa image get` reads complete stored Color Values from an individual Cel Image,
including hidden pixels and RGB under zero alpha, or reads a native composite of an
explicit Frame. Both return the same canonical Snapshot: a local `(0,0,width,height)`
Rectangle and complete rows of `{length,color}` runs. The Result reports the source
Rectangle and Coordinate Space separately. RGB uses `rgba`, Grayscale uses
`grayscale`, and Indexed retains `palette-index` with mask and Effective Palette facts.

Individual reads require an existing raster Cel and an in-bounds Image Pixel Rectangle.
Composite reads require an in-bounds Canvas Pixel Rectangle and `layer_composition`:
`{"mode":"visible"}` uses saved visibility; `{"mode":"include","layers":[{"layer_path":[1]}]}`
uses the union of exact Layer selectors. An included Group includes hidden descendants;
ancestors retain their native opacity, Blend Mode, and stacking context. Composition
uses native Tilemap rendering, excludes Reference Layers as the native renderer does,
and restores temporary visibility and Group-composition preferences. Individual reads
and replacement support Reference Images but reject raw Tilemap Images. Reads never
save the Source.

Each composite request also requires `output_color_mode: preserve|rgb`.
`preserve` uses the Source Color Mode and its native composition semantics; Indexed
output selects indexes and does not promise RGB Blend Mode/opacity equivalence.
`rgb` renders directly into a separate RGB Image for an RGBA visual observation.
It retains the Source Color Space and does not assign or convert a Color Profile.
The Result's `source.color_mode` and `source.mask_color` describe the Source;
top-level Color Mode and mask describe the output. Effective Palette facts identify
the Indexed Source's requested Frame basis; their `indexes` are empty for RGB output
because blended pixels do not retain a Palette Index identity.

For preserve-Indexed composition with a nonzero Transparent Color Index, Image Get
temporarily exchanges index zero with that index in its private loaded document,
renders through Aseprite, then restores the original index numbering in the
Snapshot. The requested Frame's Effective Palette must contain the Transparent
Color Index and every index in the returned Snapshot. A missing entry returns
`image_composition_unsupported`; Image Get does not extend the Palette or switch
to RGB. This route preserves native Indexed index-selection semantics, including
the Layer tree, and leaves the Source file unchanged. Select `rgb` for visual
observation or individual Get for exact stored indexes.

Without `snapshot_destination`, the inline Operation Limit is 4096 pixels. Larger
reads require an explicit `.json` destination with `if_exists: fail|replace` and
publish the entire Snapshot as one JSON Artifact. Smaller reads can also select this
transport. `image replace` accepts `input.kind: inline` with `snapshot`, or
`input.kind: artifact` with `path`; both use the same Snapshot schema. Replacement
requires the complete Image bounds and the same Color Mode, ignores editor Selection,
and preserves Cel geometry and native sharing. It supports regular Transparent,
Background, and Reference Images; Background colors must remain opaque. The native
file is saved and reopened before Target Commit, and any preservation failure blocks
publication. Under [#20's current scope](https://github.com/aigengame/aseprite-automation/issues/20),
replacement excludes Source documents with any Group whose opacity is not `255` or
Blend Mode is not `NORMAL`. This includes hidden Groups and Groups outside the target
Cel's ancestry, even for an unchanged Snapshot. Aseprite 1.3.18.5 batch saving loses
these properties; replacement refuses publication and leaves Source and any existing
Target unchanged. Image Get remains available under its own contract.
[#117](https://github.com/aigengame/aseprite-automation/issues/117) tracks native save support.

`spa image crop` requires a positive `rectangle` fully contained in the source
Image. `coordinate_space` is `image-pixel`; the Rectangle uses source Image Pixel
coordinates. `position_policy` is required: `preserve_canvas_pixels` adds the
Rectangle origin to every sharing Cel position, while `keep_cel_position` keeps
the Cel origin. Crop never pads or expands an Image.

`spa image canvas-resize` requires exact positive `width` and `height`, an integer
`offset`, an explicit mode-compatible `fill` Color Value, and
`coordinate_space: "image-pixel"`. The offset places source Image Pixel `(0,0)` in
the target Image Pixel space. Stored pixels copy 1:1; pixels outside the target
are discarded, and uncovered pixels keep the fill. An empty intersection is a
valid fill-only result. Indexed fill must name an existing Palette Index in every
sharing Cel's Effective Palette. No implicit color conversion or compositing occurs.
Its required `position_policy` is `keep_cel_position` or `preserve_source_canvas`;
the latter subtracts the offset from every sharing Cel position.

Both Operations preserve links and change the Image and all affected Cel positions
as one Mutation. They reject absent Cels, Group, Background, Reference, and Tilemap
Layers. Dimensions are 1–65535; request coordinates and offsets are signed 32-bit
integers. A resulting Cel position outside the native signed 16-bit range is refused.
Results report source/target bounds, copied rectangles, discarded source regions,
uncovered target regions, native content digests, and every affected Cel's old/new
Canvas Pixel positions and Image dimensions. Empty intersections are reported as
`{x:0,y:0,width:0,height:0}` in each Image Pixel space. Save/reopen verification runs
before Target Commit; the Sprite canvas size is unchanged.

```sh
uv run spa image crop --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"cropped-image.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"coordinate_space":"image-pixel","rectangle":{"x":1,"y":1,"width":8,"height":8},"position_policy":"preserve_canvas_pixels"}'
uv run spa image canvas-resize --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"padded-image.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"coordinate_space":"image-pixel","width":32,"height":32,"offset":{"x":4,"y":4},"fill":{"kind":"rgba","red":0,"green":0,"blue":0,"alpha":0},"position_policy":"preserve_source_canvas"}'
```

`spa image flip` requires `axis: "horizontal"` or `"vertical"`. It flips the
whole Image once, including pixels outside the current Selection, and preserves
Image dimensions and every sharing Cel's placement. Cels on regular Transparent,
Background, and Reference Layers are supported; Tilemap and absent Cels are rejected.

`spa image rotate` accepts integer `angle: 90`, `-90`, or `180` on regular
Transparent Layers only. It requires `position_policy: {"kind":"keep"}` or
`{"kind":"pivot","pivot_x":1,"pivot_y":0}`. The pivot is a signed 32-bit
integer point in the old Image Pixel space and may lie outside the Image.
Rotation uses the following exact pixel mappings for old dimensions `W` by `H`:

| Angle | Old `(x, y)` becomes | New dimensions |
| --- | --- | --- |
| `90` (clockwise) | `(H - 1 - y, x)` | `H` by `W` |
| `-90` (counterclockwise) | `(y, W - 1 - x)` | `H` by `W` |
| `180` | `(W - 1 - x, H - 1 - y)` | `W` by `H` |

`keep` retains Cel placement. `pivot` maps the declared point by the same rule
and applies `old_pivot - rotated_pivot` to every sharing Cel's Canvas Pixel
position. There is no interpolation or rounding. A resulting Cel position outside
the native signed 16-bit range is rejected before publication.
The `image_rotate_position_out_of_bounds` failure reports the attempted Canvas
Pixel position and the inclusive `allowed_minimum`/`allowed_maximum` for each axis.
Both operations preserve stored pixel values, Color Mode, native links, Cel
opacity and z-index, and unrelated Cels. Their results include before/after Image
content digests, Image sizes, Canvas Pixel bounds and positions, affected Cel
states and links, and verification of the staged file after save/reopen. They use
the same explicit Source/Target publication intent as Image Resize.

`spa tag list` and `spa tag get` inspect stored Tags with a one-based current
`tag_index`. `get`, `set`, and `remove` accept exactly one of `tag_index` or
`tag_name` inside `target`; a name must match exactly once. `spa tag add`
requires an inclusive `from_frame`/`to_frame` range, native `direction`, and
`repeats` (0–65535). `spa tag set` changes only supplied Tag properties. Add
and set return the persisted Tag and its index after reopening; remove returns
the removed Tag with its former index and the remaining Tag list. Native zero
repeats stays a stored value without an inferred playback sequence. Indexes
are snapshot-relative and can change after range edits. Mutations use the same
explicit Source/Target publication intent as Frame authoring.

`spa palette list` reports the ordered Palette Changes, their RGBA Entries, and
inclusive effective Frame Ranges. `spa palette get` takes a one-based
`frame_number` and returns both that requested Frame and the supplying
`palette.palette_frame_number`. Palette Indexes are zero-based.

`spa palette set` takes an exact existing `palette_frame_number` and a nonempty
`entries` list of `{index, color: {red, green, blue, alpha}}` edits. Each index
occurs once and must already exist. It recolors Entries without resizing the
Palette or rewriting Indexed pixels. The result reports the reopened Palette,
its effective range, and all persisted change points. Source/Target publication
intent is explicit, as for other mutations. These operations are standalone;
their Descriptors do not declare Plan eligibility.

```sh
uv run spa palette get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","frame_number":4}'
uv run spa palette set --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"recolored.aseprite","in_place":false,"overwrite":false,"palette_frame_number":1,"entries":[{"index":1,"color":{"red":240,"green":80,"blue":40,"alpha":255}}]}'
```

Palette edits verify exact RGBA Entries and change points after save/close/reopen
in RGB, Grayscale, and Indexed documents. They reject publication if native
behavior changes the global Transparent Color Index, removes an adjacent equal
Palette Change, or changes other document content. Same-value edits are allowed
when those invariants hold. No hidden remap or Palette Change creation occurs.
On the tested Aseprite 1.3.18.5 baseline, `spa info` reports add/remove as native
lifecycle Capability Gaps: public Lua has no change-point creation/deletion seam.
These gaps do not indicate executable discovery failure and do not register
callable commands. A future public seam needs save/close/reopen evidence before
admission; the current boundary does not prevent that extension.

`spa palette resize` targets an exact existing `palette_frame_number` and a
positive `size`. The required `entries` list supplies exactly the new indexed
RGBA Entries for growth; use an empty list for shrink or an unchanged size.
Shrink refuses indexes still used by applicable Cel or Tile Images, including
Reference Cels and unused Tiles, and cannot remove the Transparent Color Index.
Use an explicit remap first. Other Palette Changes and all Image content stay intact.

`spa palette remap` applies an explicit `mapping` list of `{old_index, new_index}`
to the whole Indexed Sprite. Each old index occurs once; unlisted indexes stay
unchanged, and several old indexes may map to one destination. Mapped indexes
must fit native Indexed storage (0–255), destinations must exist in every
Effective Palette, and the resulting Transparent Color Index must exist in
every Palette Change. Palette colors themselves do not change.

`spa palette reorder` uses the same mapping shape but requires a complete
bijective permutation, including unchanged indexes. With `scope: "sprite"`,
the permutation must match every Palette's size and applies to all changes and
Indexed Images. With `scope: "palette-change"`, supply an exact
`palette_frame_number`; the Transparent Color Index stays fixed. A shared Image
whose pixels would change outside that change's effective range causes the whole
request to fail, with the conflicting Cel and Tile uses in the failure details.
RGB and Grayscale reorder changes Palette Entries without rewriting Image pixels.

Mapping resolves unique Images once, including Linked Cels, Reference Cels, and
Tileset Images. It preserves Tilemap indexes and flags, sharing, and Tile metadata.
Results report old/new mappings, transparency, every affected Image's uses, and
before/after content digests. All three operations are standalone and verify their saved and reopened output
before Target Commit. They do not add Palette Changes or choose nearest colors.

```sh
uv run spa palette resize --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"smaller.aseprite","in_place":false,"overwrite":false,"palette_frame_number":1,"size":4,"entries":[]}'
uv run spa palette remap --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"remapped.aseprite","in_place":false,"overwrite":false,"mapping":[{"old_index":3,"new_index":0}]}'
uv run spa palette reorder --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"reordered.aseprite","in_place":false,"overwrite":false,"scope":"sprite","mapping":[{"old_index":0,"new_index":0},{"old_index":1,"new_index":2},{"old_index":2,"new_index":1},{"old_index":3,"new_index":3}]}'
```

### Palette files and Color Quantization

`spa palette import` replaces one exact existing `palette_frame_number` with a
`palette_file: {"format":"gpl"|"png","path":"..."}`. GPL includes the Aseprite
RGBA extension. PNG must be Indexed (Color Type 3); its full PLTE/tRNS tables,
including duplicate and unused Entries, are retained. Missing tRNS alpha values
mean 255. Import preserves Sprite Color Mode, stored pixels, and the Sprite's
Transparent Color Index. Format choice does not request a Color Profile conversion.
It refuses unsafe Indexed Palette uses,
malformed input, and native data loss before Target Commit. Entry names and file
layout are not part of the color-payload guarantee.

`spa palette color-quantization` replaces an exact existing Palette Change with
native colors generated from **all Frames and their visible Layer composition**.
It requires `max_colors` (1–256), `with_alpha`, `rgb_map_algorithm` (`default`,
`rgb5a3`, or `octree`), and `new_layer_blending_method`. Native `default` resolves
to `octree` in the tested runtime. Palette Picks do not limit generation; the
temporary Picks, active Frame, and blending preference are restored. Results
report requested and actual size, complete Entries, render and affected Frames,
and Indexed transparency facts. Indexed candidates that change the global mask
or leave invalid stored indexes are refused; callers must explicitly remap first.
Any native candidate above `max_colors` is also refused. Import and quantization
publish a Sprite only if save/reopen retains the complete Palette timeline.
On the tested Aseprite 1.3.18.5-dev runtime, Octree can return three Entries for a
one-color request, and small fully opaque Grayscale Palettes can expand to 256
Entries on save/reopen. These cases return `palette_quantization_rejected` or
`palette_persistence_failed`; SPA does not change the requested algorithm, add
colors, or patch the native file to make them pass.

`spa palette export` produces a verified **Palette Artifact**, from either an
Effective Palette or an explicit quantization request on a disposable Sprite.

Effective Palette export requires the native Palette file capability. Only the
`color-quantization` source branch also requires native quantization; the Surface
Manifest reports a Capability Gap for that branch when it is unavailable.

```sh
spa palette export --input-json '{
  "source_sprite_file":"sprite.aseprite",
  "palette_source":{"kind":"effective","frame_number":2},
  "destination":{"format":"png","path":"colors.png","if_exists":"fail"}
}'
spa palette export --input-json '{
  "source_sprite_file":"sprite.aseprite",
  "palette_source":{"kind":"color-quantization","palette_frame_number":1,
    "max_colors":16,"with_alpha":true,"rgb_map_algorithm":"octree",
    "new_layer_blending_method":true},
  "destination":{"format":"gpl","path":"generated.gpl","if_exists":"replace"}
}'
```

Both file formats support RGB, Grayscale, and Indexed Source Sprites. Indexed PNG
holds 1–256 ordered Entries; larger Palettes can use GPL. Export independently
decodes the staged file and checks every Entry before publication. It leaves
Source bytes unchanged, including when native generation would produce an unsafe
Sprite candidate: only the Palette Artifact is published. These operations are
standalone and do not participate in an Operation Plan.

### Change Color Mode

`spa sprite change-color-mode` declares a `conversion.source_color_mode` expectation
and a `conversion.target` branch. The live Sprite must match the source expectation.
The same `conversion` input is available in a `sprite change-color-mode` Plan Step.

| Source → Target | Required target fields besides `color_mode` |
| --- | --- |
| Same mode | None; reports `changed: false` and unchanged content |
| RGB / Indexed → Grayscale | `to_gray`: `luma`, `hsv`, or `hsl` |
| Grayscale / Indexed → RGB | None |
| Grayscale → Indexed | `rgb_map_algorithm`, `color_best_fit_criteria` |
| RGB → Indexed | `rgb_map_algorithm`, `color_best_fit_criteria`, `dithering` |

RGB Map Algorithm accepts `default`, `rgb5a3`, or `octree`. Color Best Fit Criteria
accepts `default`, `rgb`, `linearizedRGB`, `ciexyz`, or `cielab`. These are explicit
native choices; omission and inapplicable fields are rejected. On the verified
Aseprite baseline, native RGB Map `default` resolves to `octree`. Existing Effective
Palettes supply conversion; this operation does not generate a Palette.

Dithering is one of `{algorithm: "none"}`, `{algorithm: "ordered"}`, `{algorithm: "old"}`,
or `{algorithm: "error-diffusion", dithering_factor: 0.5}`. Error Diffusion requires a
finite factor from 0 through 1 and accepts no matrix. Its result includes the supplied
factor and native effective integer percentage. Ordered/old optionally take
`matrix: {kind: "installed", id: "bayer4x4"}` or
`matrix: {kind: "file", path: "/absolute/matrix.bmp"}`; neither accepts a factor.
An omitted matrix means native Bayer 8×8, reported with `native-default` provenance.
Explicit `matrix: null` is rejected.
Installed IDs resolve uniquely among the selected Aseprite installation's
`data/extensions` manifests; SPA starts with isolated user configuration. A custom
matrix outside that installation can be selected by file path. Requested files are
snapshotted, loaded by Aseprite, and checked before conversion. Missing, ambiguous,
unreadable, or invalid matrices fail without native fallback.

```sh
uv run spa sprite change-color-mode --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"indexed.aseprite","in_place":false,"overwrite":false,"conversion":{"source_color_mode":"rgb","target":{"color_mode":"indexed","rgb_map_algorithm":"default","color_best_fit_criteria":"default","dithering":{"algorithm":"none"}}}}'
```

Results report complete before/after Cel and Tile Image facts, shared Image numbers,
Effective Palette change points, Transparent Color Index, Palette Index counts,
and requested/effective mapping choices. Image content is a native-byte FNV-1a 64-bit
digest. Image numbers address one observation and are not persistent identifiers.
Linked Cels use their native representative Frame's Palette; Tiles use Frame 1.
Tilemap cell indexes are preserved. Native conversion to Indexed makes Cel opacity
255; conversion to Grayscale replaces Palette Changes with the native grayscale
Palette. These effects are reported and verified after save/close/reopen. Plan
Steps report live evidence with `persisted_reopen_verified: false`; their enclosing
Plan verifies the final document, including Tile Images, before one Target Commit.

### Color Profiles

`spa sprite assign-color-profile` takes `profile: {kind: "none"}`, `{kind: "srgb"}`,
or `{kind: "icc", icc_file: "/path/profile.icc"}`. It changes the Color Profile while
preserving stored Image pixels, Palette Entries, and Tile pixels. `spa sprite
convert-color-profile` invokes native conversion within the limited matrix below.
Both use explicit `source_sprite_file`, `target_sprite_file`, `in_place`, and
`overwrite` fields and verify save/close/reopen before Target Commit.

ICC inputs must be readable, valid profiles. Assign also supports validated LAB ICC
metadata and valid ICC files excluded from Convert, without transforming stored colors.

| Source Profile | Admitted Convert targets |
| --- | --- |
| Encoded None | Built-in sRGB |
| Built-in sRGB | Built-in sRGB; fixed linear-sRGB ICC |
| Fixed linear-sRGB ICC | Built-in sRGB; the same fixed linear-sRGB ICC |
| Fixed Display P3 ICC | Built-in sRGB; the same fixed Display P3 ICC |

The fixed files are [linear_srgb.icc](src/spa/kernel/color/profiles/linear_srgb.icc)
and [display_p3.icc](src/spa/kernel/color/profiles/display_p3.icc), also included in
the installed package. Any path containing the exact file bytes works. Other encodings
or metadata changes, even with the same profile name, are outside this Convert set.
Display P3 is the exact file verified for #103's canonical sRGB preparation path.
Built-in sRGB is not an arbitrary sRGB ICC file.

An unlisted Source ICC returns `color_profile_source_unsupported`. An unlisted target
ICC or conversion direction returns `color_profile_file_failed` with reason
`unsupported_profile` or `unsupported_conversion`. Non-RGB targets retain the static
`unsupported_color_space` refusal. These refusals preserve Source and any existing
Target, including in-place execution and Plan Steps after Assign. Assign changes
interpretation and cannot replace an unsupported requested transform.

The result reports the input path,
byte size, SHA-256, native name, and equality with the effective Sprite profile.
Results distinguish `source_profile`, `requested_profile`, and `effective_profile`;
`profile_changed` is independent of content changes. Each Cel Image, Palette Change,
and Tileset Tile has before/after content digests and a `changed` flag. Palette
observations also list changed Entry indexes. On the tested 1.3.18.5 runtime, native
Convert leaves Tileset pixels unchanged; this is reported explicitly. See the
[profile evidence](docs/evidence/issue-34-color-profile.md) for Color Mode behavior
and the batch loader's treatment of encoded None. Supported same-profile requests
and content-dependent no-ops are valid; changed-pixel counts do not determine success.
These operations do not add profile conversion to PNG Export.
Conversion requires a probed native converter. The current Linux CI build uses
`LAF_BACKEND=none`; it is expected to report a conversion Capability Gap and reject
Convert, while retaining Assign. Native conversion is verified on the macOS bundle.

```sh
uv run spa sprite assign-color-profile --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"untagged.aseprite","in_place":false,"overwrite":false,"profile":{"kind":"none"}}'
uv run spa sprite convert-color-profile --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"converted.aseprite","in_place":false,"overwrite":false,"profile":{"kind":"icc","icc_file":"/path/profile.icc"}}'
```

### Operation Plans

`spa plan check` validates a bounded Plan, including current Source and Target path
conditions, ICC file readability and validity, and fixed Convert target membership,
without starting Aseprite. Native
profile loading and document-dependent conversion checks occur during `spa plan run`, which
executes up to 64 Sprite-bound `sprite create`, `sprite get`, `frame list`,
`frame get`, `frame add`, `frame duplicate`, `cel add`, `cel set`, `motion apply`,
`paint apply`, `sprite change-color-mode`, `sprite assign-color-profile`,
and `sprite convert-color-profile` Steps
on one live Sprite in one Aseprite process. A read Plan publishes no file. A mutating
Plan declares one Target Sprite File; the staged file is reopened and verified before
one Target Commit. A failed Step publishes no target. Typed Cel, Color Mode, and Color Profile refusals identify the
one-based Step in `details.step_number`; execution failures use
`details.failed_step` when a Step was active. Each Paint Step retains its own
256-pixel Operation Limit. A Plan with an
existing Source may edit in place only with `in_place: true` and `overwrite: true`.
Plans reject a Source alias that traverses the Target publication entry for either
`in_place` value. An explicit in-place edit uses the same Source and Target entry.

A `cel set` Step accepts the standalone `target`, `position`, `opacity`, and
`z_index` fields. It retains the standalone target rules and native Linked Cel
effects. Its `before_cels`, `affected_cels`, and `cel` facts describe that Step's
live state. The Step reports `persisted_reopen_verified: false`; the enclosing Plan
reports persistence only after its final save/reopen gate. Source/Target paths,
runtime settings, and overwrite intent belong to the Plan rather than its Steps.

A `motion apply` Step accepts the same `layer`, range, and curve fields as the
standalone operation. It resolves targets and captures baselines when that Step
starts. Use separate Steps for different Layers. Its before/after facts describe
that Step, with `persisted_reopen_verified: false`; later Steps may change those
facts. Final verification compares the final live Sprite with the reopened file.

`spa export image` renders one explicit Frame of the full canvas with persisted visible
Layers. It accepts RGB Source Sprites with no Color Profile or sRGB. It rejects
Tilemap Images in the selected Frame, including hidden Layers. It preserves native
Alpha values, verifies the staged PNG with an independent decoder, and requires
`if_exists: fail` or `replace` before publication.

`--aseprite` and `SPA_ASEPRITE_EXECUTABLE` name an executable file, not a macOS
`.app` directory. When `--aseprite` is absent, SPA checks
`SPA_ASEPRITE_EXECUTABLE`, then `aseprite` on `PATH`. `spa schema` is the source
of truth for the installed callable Operations and their contracts.
`spa info` reports the selected Aseprite version, `app.apiVersion`, embedded Lua
language version, fixed scripting, file I/O, and JSON probe prerequisites, and
independently observed runtime capabilities. A prerequisite failure uses the typed
process or Kernel failure channel. A Lua-language or API-version mismatch, or a
capability required by the selected Operation but absent from the observation, returns
`runtime_incompatible` before the Operation executes.
Aseprite 1.3.18.5 is the current real-integration baseline, not a version allowlist.
Other releases follow Aseprite's native compatibility policy. SPA makes no additional
cross-version guarantee and runs no release-by-release compatibility test matrix.
`spa plan run` observes the selected Steps' requirements plus mandatory final Sprite
inspection requirements inside its one execution process. Incompatibility returns
`runtime_incompatible`
before any Plan Step begins. Aggregate discovery lists Plan as supported only when
the runtime supports every currently eligible Step kind. A Plan with fewer Step
kinds can still run; its selected and final-inspection requirements are checked per
request.
It also includes `access_failure_schema` for CLI failures before an Operation is
selected; each Operation entry has its own applicable `failure_schema`. Aggregate
discovery probes Aseprite, while each command's `--schema` remains available without a
runtime. For real-runtime tests, set `SPA_TEST_ASEPRITE` to that executable and
run `uv run --frozen --group test pytest -m e2e -x -vv --tb=short -rs`. See
[`docs/testing.md`](docs/testing.md) for the test ownership, verification-tier,
platform, and display-environment conventions.

Pull requests and main pushes run locked source, fast-test and distribution checks.
The separate **Native E2E** workflow verifies the current PR merge result on demand
before merge and runs a weekly regression on main. Routine CI success does not
replace that explicit native gate. Release verification keeps the exact-release-SHA
gate. Native runs exclude complete wizard rebuilds while retaining the small probes,
hidden-pixel regressions and other native cases. Full example rebuilds remain local
opt-in work; see the [test policy](docs/testing.md#ci-gates).
Native verification requires a prepared Aseprite binary. On a cache miss, follow
[manual runtime recovery](docs/testing.md#restore-the-aseprite-runtime). The separate
**Build Aseprite** workflow prepares the runtime; its success does not satisfy SPA
verification checks.
Releases use a reviewed version and changelog change, then
repeat all gates on the exact release commit before publishing a GitHub Release. See
[`docs/releasing.md`](docs/releasing.md) for the release and recovery procedure.

For CLI use of a binary inside a macOS `.app`, SPA prepares a temporary launch
path and links the installed `data` resources without changing the app or
leaving the caller's sandbox. The restricted macOS profile and its opt-in
real-Aseprite test are specified in
[issue #61](https://github.com/aigengame/aseprite-automation/issues/61). Linux CI
does not certify that macOS profile, and other restricted environments remain
unverified.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the integrated context map, subdomains,
module responsibilities, dependency rules, technology profile, contracts, execution
flows, trust boundary, and decision map.

## Delivery Plan

The project grows through evidence-bearing vertical slices. GitHub issues own scope,
acceptance, dependencies, evidence requirements, provenance links, curated evidence
summaries, and delivery status. Milestones group outcomes and do not imply dependencies
that are absent from issue bodies.

- [Phase 1 — Installed CLI Tracer](https://github.com/aigengame/aseprite-automation/milestone/3)
- [Phase 2 — Sprite and Animation Authoring](https://github.com/aigengame/aseprite-automation/milestone/1)
- [Phase 3 — Raster and Paint Authoring](https://github.com/aigengame/aseprite-automation/milestone/2)
- [Phase 4 — Color, Palette, and Filters](https://github.com/aigengame/aseprite-automation/milestone/6)
- [Phase 5 — Slice, Tile, and Imported Content](https://github.com/aigengame/aseprite-automation/milestone/7)
- [Phase 6 — Delivery and Agent Access](https://github.com/aigengame/aseprite-automation/milestone/5)
- [Phase 7 — Asset Pipeline Integration](https://github.com/aigengame/aseprite-automation/milestone/4)

## Non-Goals

- Editor GUI automation or a persistent interactive editor session.
- Generated Lua implementations for Ordinary Core Operations.
- An embedded model, autonomous art direction, or automatic aesthetic acceptance.
- A general workflow DAG, background job system, plug-in marketplace, or cross-document transaction.
- Godot project semantics, gameplay validation, or asset installation inside SPA.
- Bundling or redistributing Aseprite.
- A standalone REST platform. An accepted evidence-backed functional slice can later
  add bounded Artifact/resource access or MCP transport through the same Published
  Language.

## Project Documents

- [Umbrella PRD and prototype conclusions](https://github.com/aigengame/aseprite-automation/issues/1)
- [Authority governance and document dependency matrix](AUTHORITY_MATRIX.md)
- [Ubiquitous Language and strategic domain model](CONTEXT.md)
- [Integrated system architecture](ARCHITECTURE.md)
- [Testing and CI](docs/testing.md)
- [GitHub Release procedure](docs/releasing.md)
- [Accepted architecture decisions](docs/adr/)
- [Incremental command catalog](docs/command-catalog.md)
- [Aseprite CLI documentation](https://www.aseprite.org/docs/cli/)
- [Aseprite scripting documentation](https://www.aseprite.org/docs/scripting/)


## Tileset and Tilemap inspection

`spa tileset list` reports every current Tileset, its one-based `tileset_index`,
Grid, display-only `base_index`, Tile count, and all referencing Tilemap Layers.
`spa tileset get` accepts exactly one `target.tileset_index`, exact unique
`target.tileset_name`, or `target.layer` using the existing Layer address. It
reports every current Tile index, including Empty Tile 0 and unkeyed Tiles.
`spa tileset tile get` additionally selects one `tile.tile_index` or unique
`tile.tile_key` and returns its complete Image as the existing Pixel Region Snapshot.
Tileset name and Tile Key addresses reject embedded NUL as `invalid_request` before
native execution.
Base Index changes display numbering (`tile_index + base_index - 1`), never identity.

Both Tile queries return `properties` for the default namespace (`""`),
`aigengame.spa`, and the additional names in `property_namespaces`. Each namespace
contains a typed `value`: a table of ordered key/value `entries`, or an explicit
`unavailable` observation. An empty namespace is a table with no entries. Repeated
namespace names are read once. Completeness accounts for the selected namespaces;
representation gaps remain explicit in their values.

Values distinguish nil, boolean, string, integer, number, Point, Size, Rectangle,
UUID, and table. Lua integers use decimal strings to retain precision. Tables use
typed keys and entries, so numeric keys and string keys remain distinct. A value
that the projection cannot represent is explicitly `unavailable` with a reason;
non-finite numbers are reported this way instead of silently becoming JSON null.
A non-UTF-8 string value is unavailable; an unrepresentable key makes its containing
table or namespace unavailable. Other selected namespaces remain readable.
A Tile Key that cannot be represented as text is reported as `tile_key: null`;
its property observation explains the gap, and validation reports `tile_key_invalid`.
Native file type tags, namespace enumeration, and metadata reconstruction are
outside this inspection subset. It can expand when a later authoring need and
native evidence establish the scope.

The observation follows native getter behavior. On the verified Aseprite baseline,
Tile 0's Properties getter exposes Tileset properties. Those values remain visible
as returned by the API; Tile 0 still has no SPA Tile Key.

`spa tilemap list` reports all Tilemap bindings, the complete Frame count, and every
existing Tilemap Cel without expanding Cells. `spa tilemap get` selects one exact
Layer and Frame; without `rectangle` it reports topology, including an absent Cel.
With a Rectangle it reads complete Cel-local Tile Cell coverage. Negative or
out-of-bounds regions reject without clipping. A Tilemap Cel's Canvas position,
Tileset Grid, effective Cel Grid, and full Canvas coverage are separate facts;
coverage can extend outside the Sprite Canvas.

```sh
spa tilemap get --input-json '{
  "sprite_file":"map.aseprite",
  "target":{"layer":{"layer_name":"Ground"},"frame_number":1},
  "rectangle":{"x":0,"y":0,"width":8,"height":6}
}'
```

Tile Region Snapshots declare Empty Tile as their default and include every
non-empty placement in row-major order. Each observation retains the current Tile
index and X/Y/diagonal flags, with `tile_key: null` for unkeyed or invalid-index
references. Reads never assign or repair Keys. `tileset validate` checks Tile Keys,
Image/Grid agreement, and Cell references across every bound Layer and Frame;
`tilemap validate` checks the bound Tileset and references in the selected Frame.
Both return typed Findings and a `valid` verdict without making invalid Keys
prevent inspection. A validation result is an observation, not a mutation.

The empty default represents a native Cell with both index and flags zero. A Cell
with index 0 and any flag is retained with `tile_key: null`; validation reports
`empty_tile_flags`. It can render Tile 0's Image and is never silently discarded
or repaired by inspection.

The inline limits are 4096 Tile Cells per region and 4096 Image Pixels per Tile
Image. For larger values provide `snapshot_destination` with a `.json` path and
explicit `if_exists: "fail"` or `"replace"`. The JSON Artifact has exactly the same
Snapshot schema as the inline value, with digest and byte size reported only after
verified publication. Smaller Snapshots can also be sent to an Artifact explicitly.
No region is silently truncated; no read writes the Source Sprite File. These are
current delivery choices, open to extension when future requirements justify it.
