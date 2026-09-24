# Aseprite Automation

Aseprite Automation (SPA) provides agent-facing automation for Aseprite. `SPA` is the
short project name used in documentation; `spa` is the primary executable.

> [!IMPORTANT]
> This repository is at the bootstrap stage. Disposable prototypes tested selected feasibility assumptions; [issue #1](https://github.com/aigengame/aseprite-automation/issues/1) records their conclusions and is the umbrella product requirements document (PRD). The installed CLI provides runtime discovery, Sprite creation and inspection, Layer addressing and mutation, Frame inspection and authoring, bounded Pixel Patch application, and verified RGB PNG Image Export. Feature issues own delivery contracts, evidence requirements, provenance links, curated evidence summaries, and status, while milestones group phase outcomes. [`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md) routes normative facts and document dependencies. The installed Surface Manifest reports shipped behavior.

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
uv run spa frame list --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite"}'
uv run spa frame add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"timed.aseprite","in_place":false,"overwrite":false,"frame_number":2,"duration_ms":120}'
uv run spa frame duplicate --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"timed.aseprite","target_sprite_file":"duplicated.aseprite","in_place":false,"overwrite":false,"source_frame_number":1,"cel_mode":"copy"}'
uv run spa layer list --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite"}'
uv run spa layer get --input-json '{"aseprite":"/path/to/aseprite","sprite_file":"sprite.aseprite","target":{"layer_path":[1]}}'
uv run spa layer add --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"layered.aseprite","in_place":false,"overwrite":false,"kind":"group","name":"effects"}'
uv run spa layer set --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"named.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1]},"properties":{"name":"background-art","is_visible":true}}'
uv run spa layer move --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"moved.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]},"stack_index":1}'
uv run spa layer remove --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"layered.aseprite","target_sprite_file":"removed.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]}}'
uv run spa layer merge --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"two-image-layers.aseprite","target_sprite_file":"merged.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[2]}}'
uv run spa paint apply --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","target_sprite_file":"painted.aseprite","in_place":false,"overwrite":false,"target":{"layer_path":[1],"frame_number":1},"patch":{"coordinate_space":"image-pixel","rectangle":{"x":0,"y":0,"width":2,"height":1},"runs":[{"x":0,"y":0,"length":2,"color":{"kind":"rgba","red":255,"green":0,"blue":0,"alpha":255}}]}}'
uv run spa plan check --input-json '{"plan":{"source_sprite_file":"sprite.aseprite","steps":[{"operation":"sprite get","input":{"inspection_scope":["frames","layers"]}}]}}'
uv run spa plan run --input-json '{"aseprite":"/path/to/aseprite","plan":{"source_sprite_file":"sprite.aseprite","steps":[{"operation":"sprite get","input":{"inspection_scope":["frames","layers"]}}]}}'
uv run spa export image --input-json '{"aseprite":"/path/to/aseprite","source_sprite_file":"sprite.aseprite","destination":{"path":"image.png","if_exists":"fail"},"frame_number":1,"color_mode":"preserve","color_profile":"preserve","transparency":"preserve"}'
```

`--input-json -` reads one complete JSON request object from stdin; a literal
`--input-json` value remains available for short invocations.
`spa sprite create` requires an explicit `overwrite` boolean and refuses to replace an
existing Target Sprite File when it is `false`.
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
regular Transparent Image sibling. It fixes Aseprite's experimental new-blend
behavior during the merge and restores the previous preference. All four return
before/after Layer and Cel facts, directly affected object addresses, rendered
Frame digests, and save/reopen verification before Target Commit. They are
standalone mutations and are not Plan Steps. An operation that changes no Layer
or Cel facts reports empty affected sets; Group visibility and editability
changes include descendants whose effective state changes.
`spa paint apply` accepts at most 256 addressed Image Pixels per request. It defaults
to rejecting out-of-bounds pixels; `clipping: "clip"` is the explicit clipping policy.
In-place editing requires Source and Target to name the same publication entry,
plus both `in_place: true` and `overwrite: true`.
Standalone Paint rejects a Source alias that traverses the Target publication entry
for either `in_place` value.
`spa frame add` inserts an empty Frame at a one-based position with an explicit
`duration_ms` (1–65535). A Sprite with a Background Layer also requires a compatible
`background_color`; other new Layer/Frame intersections remain absent.
`spa frame duplicate` inserts immediately after its source Frame. It preserves the
source duration unless overridden and requires `cel_mode: "copy"` or `"link"`.
Both operations report native Tag Range adjustments and verify the staged Sprite
after reopening it.
The result also reports the effective Background fill or each duplicated Cel's
Layer path and copy/link relationship.

`spa plan check` validates a bounded Plan, including current Source and Target path
conditions, without starting Aseprite. `spa plan run`
executes up to 64 Sprite-bound `sprite create`, `sprite get`, `frame list`,
`frame get`, `frame add`, `frame duplicate`, and `paint apply` Steps
on one live Sprite in one Aseprite process. A read Plan publishes no file. A mutating
Plan declares one Target Sprite File; the staged file is reopened and verified before
one Target Commit. A failed Step reports its one-based `failed_step` and publishes no
target. Each Paint Step retains its own 256-pixel Operation Limit. A Plan with an
existing Source may edit in place only with `in_place: true` and `overwrite: true`.
Plans reject a Source alias that traverses the Target publication entry for either
`in_place` value. An explicit in-place edit uses the same Source and Target entry.

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

Pull requests and `main` run locked source, fast-test, distribution, and Linux
real-Aseprite gates. Releases use a reviewed version and changelog change, then
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
