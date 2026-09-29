# Sprite Automation

This document is the Ubiquitous Language and strategic domain-model authority for Aseprite Automation. It defines shared terms, the Sprite Automation Bounded Context, Subdomains, context relationships, and strategic ownership boundaries. [`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md) owns repository artifact governance and projection rules.

`SPA` is the short project name used in documentation; `spa` is the executable.

SPA shares Aseprite terminology when Aseprite already names a concept, extends that language only when agent automation needs an explicit public meaning, and defines SPA-owned terms for its automation contracts and architecture. SPA does not create a synonym for an equivalent Aseprite concept.

## Bounded Context

SPA has one **Sprite Automation Bounded Context**. It owns agent-facing preparation of explicit raster inputs, creation, editing, inspection, validation, conversion, and delivery of Aseprite visual assets.

The context contains several architectural modules and adapters, but Command Groups, Domain Modules, the command-line interface (CLI), Model Context Protocol (MCP), Agent Skill, Lua Kernel, validation, and export are not separate Bounded Contexts.

## Subdomains

- **Sprite Authoring Core Domain:** verifiable Sprite and animation creation, editing, composition, observation, and validation. Document and Animation, Raster Authoring, Color and Palette, and Tile Authoring own the corresponding native rules. Bounded motion authoring belongs to Document and Animation; static Sprite capabilities remain in scope.
- **Asset Preparation Supporting Subdomain:** explicit input preparation policies, raster geometry and anchors, validation against a Preparation Specification, and Frozen Input and Prepared Raster facts. It composes the existing raster and color rules rather than defining another native pixel or color engine.
- **Asset Delivery Supporting Subdomain:** format-specific export, declared destination sets, verified Artifacts, and publication outcomes. It contains the existing Delivery capabilities and preserves their native semantics and verification requirements.
- **Aseprite Runtime Integration Supporting Subdomain:** executable/resource discovery, process execution, Kernel transport, diagnostics, and native integration facts.
- **Access Projection Supporting Subdomain:** CLI presentation, Agent Skill guidance, MCP projection, and any later accepted access transport derived from the same Published Language.
- **Asset Pipeline Integration Supporting Subdomain:** translation at the downstream-owned Anti-Corruption Layer and public SPA boundary.
- **Generic Subdomain:** domain-neutral configuration, serialization, filesystem, and utility code required by accepted features.

The Core Domain has the highest modeling and delivery priority. Supporting and Generic work follows current functional requirements, uses proportionate abstraction, and grows from evidence rather than an independent infrastructure roadmap. ADR-0007 establishes this investment rule; [ADR-0095](docs/adr/0095-asset-preparation-authoring-and-delivery.md) refines the strategic ownership after the wizard examples. A Supporting classification does not reduce a capability's correctness requirements or move its domain rules into a technical adapter.

Preparation, authoring, and delivery describe a useful workflow. Their Subdomains own rules and may be used independently. Native document save and Target Commit belong to mutation completion, including when no Export follows. Strategic ownership does not establish a new Operation, schema, Plan eligibility, or installed capability.

## Context relationships

### Aseprite upstream

Aseprite is the upstream language and behavior authority. SPA follows its object model, scripting API, editor semantics, file formats, and native operations where the supported non-interactive seams provide evidence.

### SPA Open Host Service

The `spa` CLI first exposes the Sprite Automation Open Host Service and Published Language. The Agent Skill and planned initial MCP access project the installed CLI surface and do not maintain independent domain contracts. A later accepted transport remains an Access Projection over the same Published Language; it does not create another domain or Operation authority.

### Asset Pipeline downstream

The developing gda Asset Pipeline consumes SPA through its own Anti-Corruption Layer and the public `spa` CLI JSON contract. SPA owns accepted input preparation rules, native authoring, and export facts. The caller or pipeline owns art-input selection, cross-tool and cross-Sprite workflow order, mapping SPA Artifact roles to project roles, installation, retry, and project acceptance. Its validation-stage commands and tactical abstractions can change without changing SPA's integration commitment.

### Art inputs and generation tools

Generation tools such as imagegen and human artists supply selected raster inputs and art decisions. An Artwork Recipe declares pose choices, timing intent, attachments, and style parameters. SPA can prepare explicit inputs and apply accepted bounded authoring rules; it does not select concepts, infer missing anatomy, or guarantee artistic continuity. Input adapters translate external representations. An Anti-Corruption Layer is warranted where a different semantic model must be isolated; internal SPA modules use shared language and directed contracts.

### gda downstream evidence

gda owns Godot import, engine, and runtime evidence. SPA validation remains evidence about Sprite/Aseprite output and does not become a Godot runtime claim.

## Architecture projection

[`ARCHITECTURE.md`](ARCHITECTURE.md) derives the integrated module, dependency,
contract, and execution view from this strategic model and the accepted ADRs. It does
not create a second domain or decision authority.

This document is the canonical current strategic model. ADRs retain the decisions and
rationale that establish or change that model. A proposed decision starts from the
current model; accepting a strategic change requires updating this document in the same
change.

## Ubiquitous Language

Every term below has one of three origins:

1. **Shared Aseprite language** keeps the identity and meaning that Aseprite already
   publishes. Making an input source, serialization, or unit explicit does not create a
   new concept; a `SPA use` note records that mapping without a second definition.
2. **SPA extensions of Aseprite language** name an independently identifiable value,
   distinction, or lifecycle that Aseprite does not publish, but that is based on native
   Aseprite concepts. Each extension states its native base and the meaning that SPA adds.
3. **SPA automation language** names contracts, workflow concepts, and architecture
   that belong to SPA rather than to Aseprite.

Aseprite's editor documentation and public CLI and Lua API establish public names.
When those surfaces use different names, this glossary records the mapping. Source code
and the `.aseprite` file format can establish native behavior, but an internal class or
enum name does not by itself become a public SPA term.

### Shared Aseprite language

Terms in this section retain Aseprite's meaning. A `SPA use` note states how SPA exposes
or disambiguates the same concept; it does not define an equivalent replacement.

#### Document and animation

**Sprite**
An Aseprite document containing Frames, Layers, Cels, Palettes, Tags, Slices, Tilesets,
Grid, Color Mode, Color Profile, and related properties.
_SPA use_: A Sprite is not a host path or an exported Artifact.

**Layer**
An Aseprite timeline and stacking object. Aseprite exposes properties such as
`isImage`, `isGroup`, `isTilemap`, `isTransparent`, `isBackground`, and `isReference`.
_SPA use_: SPA preserves these overlapping properties rather than reinterpreting them as
mutually exclusive Layer kinds.

**Transparent Layer**
A Layer for which the native `isTransparent` property is true: the inverse of a
Background Layer. This property is not a mutually exclusive Layer kind; Group, Tilemap,
and Reference Layers can also be transparent. Aseprite uses `regular transparent layer`
when it needs to distinguish an ordinary pixel Layer from those other forms.

**Group Layer**
A Layer that contains child Layers and participates in hierarchy, visibility, and
compositing. Aseprite editor documentation also uses the phrase `Layer Group`.

**Background Layer**
Aseprite's native opaque Layer with its own Cel rules. It is not a Transparent Layer
whose name happens to be `Background`.

**Tilemap Layer**
A Layer whose Cels contain Tilemap Images and that references one Tileset.

**Reference Layer**
Aseprite's native reference-image Layer.
_SPA use_: Each Operation states explicitly whether it supports a Reference Layer.

**Frame**
One timeline position in a Sprite. The Lua API exposes a one-based `frameNumber` and a
duration in seconds.
_SPA use_: Public Frame Numbers are one-based. SPA represents persisted duration as
integer milliseconds and converts at the Lua boundary.

**Frame Range**
An inclusive range of Frame Numbers. Aseprite uses this meaning in editor and CLI
operations.

**Cel**
The Aseprite object at a Layer/Frame intersection. Cel absence is distinct from an
existing Cel whose Image is transparent or empty.

**Image**
Aseprite's pixel buffer object, which can be owned or shared by Cels, Tiles, and other
native structures.
_SPA use_: An Image is not a file Artifact.

**Linked Cels**
Aseprite Cels that share their Image, xy-coordinate, and opacity. Z-index remains
individual to each Cel.
_SPA use_: A raster mutation preserves this relationship unless an explicit Cel
Operation unlinks or replaces it.

**Tag**
An Aseprite named animation range with native direction and repeat properties.
_SPA use_: An Operation that consumes a Tag declares the playback context.

**Animation Direction**
Aseprite's forward, reverse, ping-pong, or ping-pong-reverse traversal behavior for a
Tag. The Lua API exposes this concept through `AniDir`.

#### Color and palettes

**Color Mode**
Aseprite's pixel representation. Sprites use RGB, Grayscale, or Indexed mode; a Tilemap
Image uses the special `ColorMode.TILEMAP` representation. Color Mode is distinct from
Color Profile and File Format.
_Avoid_: Color Handling

**Change Color Mode**
Aseprite's native operation for changing a Sprite between RGB, Grayscale, and Indexed
Color Modes. It is distinct from Color Quantization and from changing a Color Profile.

**RGB**
Aseprite's red, green, blue, and Alpha Channel pixel representation.

**Grayscale**
Aseprite's gray plus Alpha Channel pixel representation. `ColorMode.GRAY` is the
canonical Lua enum member; Aseprite v1.3.18.5 also exposes the deprecated
`ColorMode.GRAYSCALE` alias.

**Indexed**
Aseprite's Palette Index pixel representation. Indexed transparency uses Palette data
and the Sprite's transparent color index rather than an interchangeable per-pixel alpha
model.

**Alpha Channel**
The alpha component present in applicable RGB, Grayscale, Palette Entry, and File
Format behavior.
_Avoid_: Alpha Handling

**Background Color**
Aseprite's active background color used by applicable editor and scripting operations.
_SPA use_: An Operation that creates or fills a Background Layer or Background Cel
requires an explicit Color Value instead of reading ambient editor state or preferences.

**Palette**
Aseprite's indexed color table. The native document model can associate Palette values
with Frames.

**Palette Change**
A Palette value in Aseprite's native document model that becomes effective at a Frame.
It is not an independent Palette for every Frame.
_SPA use_: SPA addresses the Frame explicitly because an isolated request cannot rely
on the editor's active Frame.

**Palette Entry**
The color stored at one Palette Index in a Palette.

**Palette Index**
The stored integer value of an Indexed pixel and the address of a Palette Entry.

**Color Profile**
Aseprite uses `Color Profile` in its editor and file-format language; the Lua API uses
`ColorSpace` for the same color-space/profile concern. It is independent of Color Mode.
_SPA use_: SPA uses Color Profile in its public language and maps it to native
`ColorSpace` values.

**Assign Color Profile**
Aseprite's native operation for attaching a Color Profile interpretation without
transforming stored color values. The Lua API exposes `assignColorSpace()`.

**Convert Color Profile**
Aseprite's native operation for transforming applicable stored color values when the
Sprite changes Color Profile. The Lua API exposes `convertColorSpace()`.

**sRGB**
Aseprite's built-in standard RGB Color Profile.

**ICC Profile**
An external ICC color-profile input used by applicable native Assign or Convert
behavior.

**Color Quantization**
Aseprite's native creation of Palette colors from rendered Sprite colors. It is
distinct from Change Color Mode.

**Color Best Fit Criteria**
Aseprite's native criterion for choosing the closest Palette Entry during applicable
color mapping.

**Dithering**
Aseprite's color-conversion behavior for approximating colors through patterns or error
diffusion.

**Dithering Algorithm**
Aseprite's selected native Dithering method for an applicable color operation.

**Dithering Matrix**
An Aseprite resource used by applicable ordered Dithering or Tool behavior. It is
distinct from a Convolution Matrix.

**Dithering Factor**
Aseprite's strength input for an applicable Dithering Algorithm.

#### Geometry and selection

**Point**
Aseprite's `x`, `y` position value.
_SPA use_: The owning Operation declares the Coordinate Space.

**Rectangle**
Aseprite's `x`, `y`, `width`, `height` shape.
_SPA use_: Public Rectangles use half-open coverage. Each Operation defines whether
negative positions or empty Rectangles are meaningful.

**Selection**
Aseprite's selected pixel area. The public API exposes it as a Selection object that
operates on pixels in the Sprite canvas.
_SPA use_: SPA transports the same concept as an explicit serializable value rather
than reading hidden editor state.

**Selection Mask**
The native binary coverage of a Selection.
_SPA use_: SPA serializes the mask as the canonical coverage of its Selection value; a
preview image is derived evidence and is not the mask authority.

#### Slices and tiles

**Slice**
An Aseprite named object with ordered Frame-varying Slice Keys.

**Slice Key**
A Slice value that starts at one Frame and supplies bounds plus optional center and
pivot until another Key takes effect.

**Grid**
Aseprite's origin and cell-size geometry used by Tilemaps and other grid-aware editor
behavior.

**Tileset**
An Aseprite collection of Tiles with a Grid and Base Index that can be referenced by
Tilemap Layers.

**Tile**
An entry in a Tileset with an Image and native properties.

**Empty Tile**
The native Tile at internal index 0 that represents an empty Tilemap grid cell.

**Tile Index**
A Tile's current native position in a Tileset. It can change and is not persistent
identity.

**Base Index**
Aseprite's display and export offset for non-empty Tile numbers. It is not a Tile Index
or identity.

**Tilemap**
Aseprite's tile-based Layer content. Each Tilemap Image pixel references a Tile in the
Layer's Tileset and can include native flip flags.

#### Native authoring and files

**Brush**
Aseprite's Tool footprint and shape input.

**Ink**
Aseprite's native pixel-application behavior used by a Tool.

**Tool**
An Aseprite drawing or selection tool. `app.useTool()` drives a Tool through explicit
points, Brush, Ink, color, and target inputs.

**Filter**
An Aseprite batch pixel operation such as Brightness/Contrast, Outline, or Despeckle.
A Filter is distinct from a Tool and from a generic extension DSL.

**Filter Channels**
Aseprite's `FilterChannels` values for selecting color components or, where supported,
stored Palette Index values affected by a Filter.

**Tiled Mode**
Aseprite's horizontal and vertical wrap behavior for applicable Tool and Filter
operations.

**File Format**
Aseprite's encoded input or output format and its native options. File Format is
distinct from Color Mode and Color Profile.
_Avoid_: Static Image Format

### SPA extensions of Aseprite language

These terms add public agent-facing meaning to the native concepts named in each
definition. They do not replace Aseprite's object model or algorithms.

#### Color projection

**Color Value**
SPA's discriminated public representation of an Aseprite RGB value, Grayscale value, or
Palette Index. It preserves the active Color Mode instead of normalizing every value to
RGBA. It is not a replacement for the native Lua `Color` object.

**RGB Map Algorithm**
SPA's public name for the choice exposed by Aseprite's native `rgbmap` command parameter
and editor phrase `RGB to palette index mapping`. The public `rgb_map_algorithm` field
and requested/effective result distinguish explicit agent intent from native fallback.

**Effective Palette**
The Palette Change that applies at a requested Frame. SPA resolves and reports this
value when native color behavior depends on a Frame.

**Transparent Color Index**
SPA's explicit name for the Sprite-wide Palette Index exposed by the Lua API as
`Sprite.transparentColor`. It is distinct from the Alpha Channel of a Palette Entry.

#### Coordinates and selection projection

**Coordinate Space**
The named coordinate system that gives a Point or Rectangle meaning in a public
Operation.

**Canvas Pixel**
A pixel coordinate in Sprite canvas space.

**Image Pixel**
A pixel coordinate local to one Image.

**Tile Bitmap Pixel**
A pixel coordinate inside a Tile Image.

**Tile Cell**
A coordinate in a Tilemap Cel's logical grid. It is not a Canvas Pixel or Tile Bitmap
Pixel.

**Selection Application**
An Operation's explicit use of a Selection value to constrain affected Canvas Pixels.
An absent Selection is unrestricted, an empty Selection affects no pixels, and an
all-canvas Selection includes every Canvas Pixel.

#### Tile and raster projection

**Tile Key**
SPA's Tileset-scoped persistent Tile identity used when Aseprite provides no suitable
native identity. It is stored in the documented SPA custom-properties namespace and
remains distinct from the current Tile Index.

**Tile Placement**
SPA's structured representation of one native Tilemap grid-cell value: Empty Tile or a
Tile reference plus native horizontal, vertical, and diagonal flip flags.

**Tile Region Snapshot**
A complete bounded Tile Cell Rectangle with a declared Empty Tile default and canonical
non-empty Tile Placements.

**Tilemap Patch**
A bounded set of explicitly addressed Tile Cell changes that leaves unlisted cells
unchanged.

**Raster**
The shared pixel domain through which SPA observes and transforms Aseprite Images and
expresses Tool and Filter intent. Raster is not a second Image object model.

**Pixel Region Snapshot**
A complete bounded Raster value whose serialized pixels use local Image Pixel
coordinates from `(0,0)`. The owning Operation Result reports a different source
Coordinate Space and source Rectangle separately.
_SPA use_: Individual Image observation preserves stored Color Mode and pixel values.
A composite observes rendered content in an explicitly selected output Color Mode;
an RGBA composite does not retain authored Palette Index identity.

**Pixel Patch**
A bounded set of explicitly addressed pixel changes that leaves unlisted pixels
unchanged.

**Paint Operation**
An SPA Operation that expresses raster-authoring intent and delegates applicable
gesture or controller behavior to an Aseprite Tool.

**Filter Cels Target**
The Filter-specific public target that resolves existing Cels from exact Layer and Frame
choices while preserving Aseprite's native target meaning. It is not a universal
Selector.

**Filter Application**
SPA's Filter-specific explicit choice among the native pixel, Palette Entry, or combined
application paths supported by one Filter. It is not a generic effect destination.

**Export Image Area**
The Canvas Rectangle rendered by an Export Image Operation. It is distinct from a
Selection Mask.

**Layer Composition**
The explicit Layer set and native stacking context used to render composited pixels
for Image observation or an Export Operation. Aseprite remains the compositor.

#### Targeting rule

SPA does not define a universal Selector, Locator, or Address value. Each Operation owns
the exact Aseprite-aligned target fields and cardinality that its behavior requires.
Layer, Tag, Slice, and Tileset Operations can therefore use different native IDs,
indexes, names, paths, or references without creating four parallel `Addressing`
concepts.

### SPA automation language

#### Public contract

**Operation**
One typed agent-facing SPA capability with declared inputs, outputs, failures, side
effects, targets, Operation Limits, and Operation Determinism.

**Ordinary Core Operation**
An Operation whose Core Operation Semantics execute through one fixed packaged Lua
handler. It excludes capabilities implemented wholly by Application use cases and
`script run`.
The established name identifies an execution category, not membership in the Sprite
Authoring Core Domain. Asset Delivery Operations with this execution binding retain
the same packaged-handler authority. Wholly application-owned preparation behavior
does not require a native handler unless it invokes native semantics.

**Operation Descriptor**
The registration authority for a structured public capability's identity, schemas,
metadata, presentation projection, and execution definition. An Ordinary Core
Operation binds one packaged Lua handler; another capability can bind an Application
use case or the separate `script run` adapter path without a Kernel binding.

**Runtime Requirements**
The Lua language profile, minimum Aseprite `app.apiVersion`, and set of
Aseprite-provided capabilities declared by a runtime-backed Operation Descriptor. SPA
establishes probe and transport prerequisites through a complete probe response and
preserves independently observed native capabilities. The Application compares those
capabilities, the Lua language, and the API version with the selected Descriptor before
executing the Operation.

**Command Group**
A CLI navigation grouping based mainly on Aseprite language. It does not define a
Domain Module or Bounded Context.

**Open Host Service (OHS)**
The public service boundary first exposed by the `spa` CLI.

**Published Language (PL)**
The versioned Operation Request, Operation Result, Failure Envelope, metadata, Artifact,
and Surface Manifest schemas shared with callers.

**Surface Manifest**
The installed aggregate description of callable Operations and applicable Capability
Gaps. Its Operation entries are the runtime authority for shipped capability; a Gap
does not register an Operation. A compositional Operation is listed as fully supported
only when the runtime supports every currently eligible Step kind; a particular
request can need fewer capabilities and remains independently executable.

**Operation Request**
The complete typed input to one Operation after public absent, null, and default
semantics are resolved.

**Operation Result**
The typed success value of one Operation, including verified domain facts and produced
Artifacts.

**Failure Envelope**
The disjoint typed failure result containing a stable Failure Code, a well-defined
Failure Category, applicable Failure Details, and Diagnostics.

**Failure Code**
A stable machine-oriented identifier used for caller decisions.

**Failure Category**
A stable class of public failures for process exit behavior and cross-code caller
policy; it does not replace the more specific Failure Code. `kernel_protocol` names
failures of the private Kernel Protocol response, not arbitrary protocol, process,
or Kernel handler failures.

**Failure Details**
Code-specific structured facts needed by a caller to understand or recover from one
failure.

**Diagnostics**
Human-oriented explanatory text and bounded process output. Diagnostics are not a
machine contract.

**Execution Kind**
The side-effect and trust classification of an Operation: `read`, `mutation`, `export`,
or `script-run`. Validation is a read purpose, not a separate Execution Kind.

**Operation Determinism**
The declared classification of the repeatability guarantee SPA can make for an
Operation.
`deterministic` and `native-stochastic` apply to `read`, `mutation`, and `export`.
`caller-defined` applies only to `script-run` and states that SPA makes no claim about
the caller's script repeatability or randomness source. All other Execution Kinds
prohibit that value.

**Capability Gap**
A structured, versioned, evidence-backed fact that the supported Aseprite public
non-interactive seams cannot provide a capability faithfully. The capability can be
unimplemented because of that limitation. Lack of investigation is not a Gap, and the
absence of a Gap does not prove support. A Gap can be reopened by new native evidence.

#### Mutation and validation

**Inspection Scope**
The domain-specific requested coverage of an inspection and the completeness promised
for it.

**Validation**
A read behavior that evaluates declared rules and returns Validation Findings without
treating findings as invocation failure.

**Validation Finding**
One typed rule result associated with an exact domain subject and evidence.

**Postcondition**
A declared condition that must hold after execution and before Target Commit or Artifact
publication.

**Operation Limit**
A functional limit expressed in units intrinsic to one Operation, such as pixels, Tile
Cells, Frames, or Plan Steps.

**Execution Guard**
An adapter-level limit on one Aseprite invocation, such as timeout or captured output.
It is not a global quota or policy system.

**Source Sprite File**
An existing `.aseprite` file opened as mutation input.

**Target Sprite File**
The declared `.aseprite` file published by a successful creation or mutation.

**In-place Mutation**
Explicit caller intent to use the Source Sprite File as the Target Sprite File.

**Staged Sprite File**
A temporary sibling used for save and verification before publication.

**Target Commit**
The final replacement of a validated Staged Sprite File into its declared Target Sprite
File.

**All-or-Nothing Mutation**
The guarantee that an Ordinary Core Operation with Execution Kind `mutation` succeeds
for its complete resolved target set or produces no Target Commit.

**Artifact**
A produced and verified file reported by the owning Operation Result with path, role,
format, byte size, and digest.

**Export Destination**
The explicit final path and overwrite intent for an exported Artifact.

**Preview Artifact**
An image Artifact produced for inspection. It supports visual review but does not prove
aesthetic quality.

#### Preparation and authored intent

**Preparation Specification**
The caller's finite declaration of the required raster geometry, color and transparency
policy, explicit Input Anchors, and applicable preparation choices. It describes the
required input result; the owning feature defines supported combinations and bounds.

**Input Anchor**
An explicitly supplied landmark in a declared raster Coordinate Space. Preparation
can use it for declared alignment and reports its position after geometric
transformations. Its artistic meaning and later attachment choices belong to the
Artwork Recipe; it is not an inferred anatomical point or an Aseprite Slice Key.

**Frozen Input**
Selected input bytes retained with declared preparation choices and the information
needed to check that a rebuild uses the same content. The owning feature chooses the
verification mechanism. It does not imply filesystem immutability, a persistent asset
registry, or an automatic generation retry.

**Prepared Raster**
A raster whose observed pixels, geometry, and Input Anchor facts satisfy the declared
Preparation Specification. Its result identifies the source and output content and
the applied choices. A produced file is reported as an Artifact; native insertion is
the separate raster-import responsibility.

**Artwork Recipe**
Caller-owned art decisions and finite composition instructions: selected poses,
appearance, timing intent, attachments, and effects. A recipe can supply explicit
values to reusable authoring capabilities without making those capabilities own the
character or its artistic quality.

**Bounded Motion Authoring**
Motion authored from explicit key values over a finite Frame range, with declared
sampling, interpolation, coordinate rounding, and native relationship behavior.
Document and Animation owns these rules. Feature contracts define supported modes
and bounds; the term does not promise anatomical interpolation or a general animation
engine.

#### Orchestration and architecture

**Operation Plan**
A bounded ordered list of eligible public Operations applied to one Sprite in one
Aseprite process and adapter unit of work.

**Plan Step**
One Operation invocation and its preconditions within an Operation Plan.

**Domain Module**
The vertical code-ownership envelope for Operations that share domain language and
reasons to change. It is not a logical layer or Command Group.

**Lua Operation Kernel**
The packaged private handler system that owns SPA Core Operation Semantics and their
mapping to Aseprite's native creation, editing, inspection, validation, conversion, and
export behavior. Standalone and Plan execution use the same Ordinary Core Operation
handlers. This execution authority applies to native Operations in Core and Supporting
Subdomains alike.

**Kernel Protocol**
The private versioned request/response transport between Python and the Lua Operation
Kernel.

**Aseprite Adapter**
The outbound adapter that owns runtime discovery, resources, process launch, Kernel
transport, diagnostics, and transport of native observations produced by packaged
handlers.

**File Adapter**
The outbound adapter that owns domain-neutral path handling, staging, file existence,
byte size, digest, publication, and cleanup. It does not decode a File Format or
interpret Sprite semantics.

**Artifact Verifier**
A format-specific outbound adapter that independently decodes typed observed facts from
staged Artifact bytes. It does not define the expected domain result or publish files.

**Agent Skill**
Version-matched guidance that teaches agents how to discover and invoke the installed
SPA Operation surface.

**MCP Adapter**
An inbound adapter that derives tools from the installed Surface Manifest and invokes
the `spa` CLI without owning Operation semantics.

**Anti-Corruption Layer (ACL)**
Translation that protects one semantic model from a different external model. The
Asset Pipeline-owned ACL translates between pipeline concepts and the public SPA
Published Language. Internal module boundaries that share SPA meanings use directed
contracts without requiring another ACL.

## Artifact authority matrix

The canonical matrix moved to [`AUTHORITY_MATRIX.md`](AUTHORITY_MATRIX.md). This
section preserves existing inbound links only; it does not own a duplicate matrix.
