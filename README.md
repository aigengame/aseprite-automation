# Aseprite Automation

Aseprite Automation (SPA) provides agent-facing automation for Aseprite. `SPA` is the
short project name used in documentation; `spa` is the primary executable.

> [!IMPORTANT]
> This repository is at the bootstrap stage. Disposable prototypes tested selected feasibility assumptions; [issue #1](https://github.com/aigengame/aseprite-automation/issues/1) records their conclusions and is the umbrella product requirements document (PRD). The installed CLI provides runtime discovery, Sprite creation, inspection, copy, resize, crop, flatten, and validation, Layer addressing and mutation, Frame inspection, authoring, and editing, Cel inspection, lifecycle, placement, and native relationships, Tag inspection and authoring, Cel-targeted Image resize, crop, canvas-resize, flip, and quarter-turn rotation, canonical Image reads and replacement, bounded Pixel Patch application, native Snapshot composition (`spa paint composite`), verified RGB PNG Image Export, animation audit, Frame comparison, and verified continuity Preview export. Feature issues own delivery contracts, evidence requirements, provenance links, curated evidence summaries, and status, while milestones group phase outcomes. [`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md) routes normative facts and document dependencies. The installed Surface Manifest reports shipped behavior.

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
- Capability Gaps are versioned, evidence-backed runtime facts. They remove unfaithful Operations from the installed Surface Manifest instead of creating silent partial support.

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

The current verified native profile supports all 19 published modes for RGB.
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

```sh
uv run spa paint composite --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"composited.aseprite","in_place":false,"overwrite":false,"target":{"layer":{"layer_path":[1]},"frame_number":1},"input":{"kind":"artifact","path":"snapshot.json"},"position":{"x":0,"y":0},"opacity":127,"blend_mode":"normal"}'
```

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
creates a full-canvas transparent Image only at an absent regular Transparent
Layer intersection. `cel clear` preserves the Cel and its Image bounds; on a
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

`spa plan check` validates a bounded Plan, including current Source and Target path
conditions, without starting Aseprite. `spa plan run`
executes up to 64 Sprite-bound `sprite create`, `sprite get`, `frame list`,
`frame get`, `frame add`, `frame duplicate`, `cel add`, `cel set`, `motion apply`, and `paint apply` Steps
on one live Sprite in one Aseprite process. A read Plan publishes no file. A mutating
Plan declares one Target Sprite File; the staged file is reopened and verified before
one Target Commit. A failed Step publishes no target. Typed Cel refusals identify the
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
run `uv run --frozen --group test pytest -m e2e -rs`. See
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
