# Sprite Automation

This document is the Ubiquitous Language and context-routing authority for Aseprite Automation. It defines shared terms and ownership boundaries. Accepted ADRs own durable decisions; feature issues own delivery scope and acceptance; the installed Surface Manifest owns shipped Operations.

SPA reuses Aseprite terminology whenever Aseprite already names a concept. An SPA term exists when agent automation needs a public contract, an ownership boundary, or an explicit distinction that Aseprite's interactive editor can keep implicit.

## Bounded Context

SPA has one **Sprite Automation Bounded Context**. It owns agent-facing creation, editing, inspection, validation, conversion, and export of Aseprite visual assets.

The context contains several architectural modules and adapters, but Command Groups, Domain Modules, CLI, MCP, Agent Skill, Lua Kernel, validation, and export are not separate Bounded Contexts.

## Subdomains

- **Sprite Automation Core Domain:** Aseprite-equivalent sprite capabilities plus agent-facing control, composition, observation, and verification.
- **Aseprite Runtime Integration Supporting Subdomain:** executable/resource discovery, process execution, Kernel transport, staging, and native integration facts.
- **Access Projection Supporting Subdomain:** CLI presentation, Agent Skill guidance, and MCP projection from the same Published Language.
- **Asset Pipeline Integration Supporting Subdomain:** translation at the downstream-owned Anti-Corruption Layer and public SPA boundary.
- **Generic Subdomain:** domain-neutral configuration, serialization, filesystem, and utility code required by accepted features.

The Core Domain has the highest delivery priority. Supporting and Generic work follows current functional requirements, uses proportionate abstraction, and grows from evidence rather than an independent infrastructure roadmap. ADR-0007 owns this investment rule.

## Context relationships

### Aseprite upstream

Aseprite is the upstream language and behavior authority. SPA follows its object model, scripting API, editor semantics, file formats, and native operations where the supported non-interactive seams provide evidence.

### SPA Open Host Service

The `spa` CLI exposes the Sprite Automation Open Host Service and Published Language. Agent Skill and MCP access project the installed CLI surface and do not maintain independent domain contracts.

### Asset Pipeline downstream

The developing gda Asset Pipeline consumes SPA through its own Anti-Corruption Layer and the public SPA JSON ABI. The pipeline owns workflow order, concept/reference handoff, produced-file roles, installation, retry, and project acceptance. Its validation-stage commands and tactical abstractions can change without changing SPA's integration commitment.

### gda downstream evidence

gda owns Godot import, engine, and runtime evidence. SPA validation remains evidence about Sprite/Aseprite output and does not become a Godot runtime claim.

## Architecture model

- **Inbound adapters** translate CLI or MCP requests into Application use cases.
- **Application use cases** coordinate domain rules, Operation Descriptors, ports, packaged Kernel capabilities, staging, and Artifact publication.
- **Domain Modules** own cohesive vertical feature slices across contract, domain, application, presentation, and Lua binding responsibilities.
- **Outbound ports** are owned by the inner contract that needs external behavior.
- **Concrete adapters** implement Aseprite, filesystem, clock, digest, and other external behavior behind those ports.
- **Bootstrap composition** binds concrete adapters and entry points.

Source dependencies point inward from inbound adapters and outward implementations toward inner-owned ports. Domain Modules do not depend on concrete adapters or each other cyclically. Application orchestration may compose several modules through explicit contracts.

## Aseprite language

### Document and animation

**Sprite**
An Aseprite document containing Frames, Layers, Cels, Palettes, Tags, Slices, Tilesets, Grid, Color Mode, Color Profile, and related properties. A Sprite is not a host path or exported file.

**Layer**
An Aseprite timeline and stacking object. Native Layer kinds include Image Layer, Group Layer, Background Layer, Tilemap Layer, and Reference Layer.

**Image Layer**
A Layer whose Cels contain raster Images. It can be transparent or converted to the Sprite's Background Layer when native constraints are satisfied.

**Group Layer**
A Layer that contains child Layers and participates in hierarchy, visibility, and compositing.

**Background Layer**
Aseprite's native opaque background Layer with its own Cel rules. It is not a transparent Image Layer named "Background."

**Tilemap Layer**
A Layer whose Cels contain Tilemap cell data and reference one Tileset.

**Reference Layer**
Aseprite's native reference-image Layer. Support depends on the Operation's declared native behavior.

**Frame**
One timeline position in a Sprite. Public Frame Numbers are one-based and persisted duration is represented as integer milliseconds.

**Frame Range**
An inclusive range of public Frame Numbers.

**Cel**
The Aseprite object at a Layer/Frame intersection. Cel absence is distinct from an existing Cel whose Image is transparent or empty.

**Image**
Aseprite's pixel buffer value owned or shared by Cels, Tiles, and other native structures. An Image is not a file Artifact.

**Linked Cels / Linked Image**
Cels that share one native Image. A raster mutation preserves that sharing unless an explicit Cel operation changes it.

**Tag**
An Aseprite named animation range with native direction and repeat properties. A Tag stores animation metadata; an Operation that consumes it declares the playback context.

**Animation Direction**
Aseprite's forward, reverse, ping-pong, or ping-pong-reverse traversal behavior for a Tag.

### Color and palettes

**Color Mode**
Aseprite's RGB, Grayscale, or Indexed representation for a Sprite or Image. It is distinct from Color Profile and File Format.
_Avoid_: Color Handling

**RGB**
Aseprite's red, green, blue, and Alpha Channel pixel representation.

**Grayscale**
Aseprite's gray plus Alpha Channel pixel representation.

**Indexed**
Aseprite's Palette Index pixel representation. Indexed transparency uses the Transparent Color Index and Palette data rather than an interchangeable per-pixel alpha model.

**Alpha Channel**
The alpha component present in applicable RGB, Grayscale, Palette Entry, and File Format behavior.
_Avoid_: Alpha Handling

**Color Value**
SPA's discriminated public representation of an RGB value, a Grayscale value, or a Palette Index. It preserves the active Color Mode rather than normalizing every value to RGBA.

**Palette**
Aseprite's indexed color table. A Sprite can contain Frame-based Palette Changes.

**Palette Change**
A Palette value that becomes effective at a Frame. It is not an independent Palette per Frame.

**Effective Palette**
The Palette Change whose value applies at a requested Frame.

**Palette Entry**
The color stored at a Palette Index in one Palette Change.

**Palette Index**
The stored integer value of an Indexed pixel and the address of a Palette Entry.

**Transparent Color Index**
The Sprite-wide Palette Index used for transparent Indexed pixels. It is distinct from the Alpha Channel of a Palette Entry.

**Color Profile**
Aseprite's color-space metadata and native Assign/Convert behavior. It is independent of Color Mode.

**sRGB**
Aseprite's built-in standard RGB Color Profile.

**ICC Profile**
An exact external ICC color-profile input used by applicable native Assign or Convert behavior.

**Color Quantization**
Aseprite's native creation of Palette colors from rendered Sprite colors. It is distinct from Change Color Mode.

**Dithering**
Aseprite's color-conversion behavior for approximating colors through patterns or error diffusion.

**Dithering Matrix**
An Aseprite resource used by applicable ordered Dithering or Paint behavior. It is distinct from a Convolution Matrix.

### Geometry and selection

**Point**
An Aseprite-aligned `x`, `y` position whose Coordinate Space is declared by the owning Operation.

**Rectangle**
An Aseprite-aligned `x`, `y`, `width`, `height` shape. SPA uses half-open coverage; each Operation defines whether negative positions or empty Rectangles are meaningful.

**Canvas Pixel**
A pixel coordinate in Sprite canvas space.

**Image Pixel**
A pixel coordinate local to one Image.

**Tile Bitmap Pixel**
A pixel coordinate inside a Tile Image.

**Tile Cell**
A coordinate in a Tilemap Cel's logical grid. It is not a Canvas Pixel or Tile Bitmap Pixel.

**Coordinate Space**
The named coordinate system that gives a Point or Rectangle meaning.

**Selection**
Aseprite's selected pixel area, represented by SPA as an explicit serializable value rather than hidden editor state.

**Selection Mask**
The canonical binary coverage represented by a Selection value. A preview image is derived evidence and not the mask authority.

### Slices and tiles

**Slice**
An Aseprite named object with ordered Frame-varying Slice Keys.

**Slice Key**
A Slice value that starts at one Frame and supplies bounds plus optional center and pivot until another Key takes effect.

**Grid**
Aseprite's origin and cell-size geometry used by Tilemaps and other grid-aware editor behavior.

**Tileset**
An Aseprite collection of Tiles with a Grid and Base Index that can be referenced by Tilemap Layers.

**Tile**
An entry in a Tileset with an Image and native properties.

**Empty Tile**
The native Tile at internal index 0 that represents an empty Tilemap cell.

**Tile Index**
A Tile's current native position in a Tileset. It can change and is not persistent identity.

**Base Index**
Aseprite's display/export offset for non-empty Tile numbers. It is not a Tile Index or identity.

**Tile Key**
SPA's Tileset-scoped persistent Tile identity used when Aseprite provides no suitable native identity. It is stored in the documented SPA custom-properties namespace and remains distinct from current Tile Index.

**Tilemap**
The Aseprite cell data contained by a Tilemap Cel and interpreted through its Layer's Tileset.

**Tile Placement**
One Tilemap cell value: Empty Tile or a Tile reference plus native flip and diagonal flags.

**Tile Region Snapshot**
A complete bounded Tile Cell Rectangle with a declared Empty default and canonical non-empty placements.

**Tilemap Patch**
A bounded set of explicitly addressed Tile Cell changes that leaves unlisted cells unchanged.

### Native authoring

**Brush**
Aseprite's Paint footprint and shape input.

**Ink**
Aseprite's native Paint behavior for applying a tool's output to pixels.

**Paint Tool**
An Aseprite gesture- or controller-driven raster operation such as Pencil, Fill, Line, Blur, or Jumble.

**Filter**
An Aseprite batch pixel operation such as Brightness/Contrast, Outline, or Despeckle. A Filter is distinct from a Paint Tool and from a generic extension DSL.

**Filter Channels**
Aseprite's selection of pixel components or, when natively supported, stored Palette Index values affected by a Filter.

**Tiled Mode**
Aseprite's horizontal and vertical wrap behavior for applicable native Paint and Filter operations.

**File Format**
Aseprite's encoded output format and its native options. File Format is distinct from Color Mode and Color Profile.
_Avoid_: Static Image Format

## SPA automation language

### Public surface

**Operation**
One typed agent-facing SPA capability with declared inputs, outputs, failures, side effects, determinism, targets, and bounds.

**Operation Descriptor**
The registration authority for an Operation's identity, schemas, metadata, presentation projection, and Lua handler binding. It does not implement native behavior.

**Command Group**
A CLI navigation grouping based mainly on Aseprite domain language. It does not define a module or Bounded Context.

**Open Host Service (OHS)**
The public service boundary first exposed by the `spa` CLI.

**Published Language (PL)**
The versioned request, Operation Result, Failure Envelope, metadata, Artifact, and Surface Manifest schemas shared with callers.

**Surface Manifest**
The installed aggregate description of callable Operations. It is the runtime authority for shipped capability.

**Operation Request**
The complete typed input to one Operation after public absent, null, and default semantics are resolved.

**Operation Result**
The typed success value of one Operation, including verified domain facts and produced Artifacts.

**Failure Envelope**
The disjoint typed failure result containing a stable Failure Code, applicable Failure Details, and Diagnostics.

**Failure Code**
A stable machine-oriented identifier used for caller decisions.

**Failure Details**
Code-specific structured facts needed by a caller to understand or recover from one failure.

**Diagnostics**
Human-oriented explanatory text and bounded process output. Diagnostics are not a machine contract.

**Operation Determinism**
The declared `deterministic` or `native-stochastic` classification of the result governed by an Operation.

**Capability Gap**
A structured, versioned, evidence-backed fact that the supported Aseprite public non-interactive seams cannot provide a capability faithfully. A Gap can be reopened by new native evidence.

### Mutation and validation

**Inspection Scope**
The domain-specific requested coverage of an inspection and the completeness promised for it.

**Validation**
A read behavior that evaluates declared rules and returns Validation Findings without treating findings as invocation failure.

**Validation Finding**
One typed rule result associated with an exact domain subject and evidence.

**Postcondition**
A declared condition that must hold after execution and before Target Commit or Artifact publication.

**Domain Bound**
A functional constraint expressed in units intrinsic to an Operation, such as pixels, Tile Cells, Frames, or Plan Steps.

**Execution Guard**
An adapter-level limit on one Aseprite invocation, such as timeout or captured output. It is not a global quota or policy system.

**Source Sprite File**
An existing `.aseprite` file opened as mutation input.

**Target Sprite File**
The declared `.aseprite` file published by a successful creation or mutation.

**In-place Mutation**
Explicit caller intent to use the Source Sprite File as the Target Sprite File.

**Staged Sprite File**
A temporary sibling used for save and verification before publication.

**Target Commit**
The final replacement of a validated Staged Sprite File into its declared Target Sprite File.

**All-or-Nothing Mutation**
The guarantee that an ordinary Mutation succeeds for its complete resolved target set or produces no Target Commit.

**Artifact**
A produced and verified file reported by the owning Operation Result with path, role, format, byte size, and digest.

**Export Destination**
The explicit final path and overwrite intent for an exported Artifact.

**Preview Artifact**
An image Artifact produced for inspection. It supports visual review but does not prove aesthetic quality.

### Raster exchange

**Raster**
The shared pixel domain used by Image observation/transformation and Paint intent. It is not a competing Image model.

**Pixel Region Snapshot**
A complete bounded raster value with explicit dimensions, Color Mode, Coordinate Space, and pixel data.

**Pixel Patch**
A bounded set of explicitly addressed pixel changes that leaves unlisted pixels unchanged.

**Paint Operation**
An Operation that expresses raster authoring intent against an explicit Cel/Image target.

**Filter Cels Target**
The Filter-specific native scope that resolves existing Cels from exact Layer and Frame choices. It is not a universal Selector.

**Layer Addressing**
Operation-specific exact Layer targeting by persistent native UUID when available, current stack path, or a name that is unique in the declared scope.

**Tag Addressing**
Operation-specific Tag targeting by current index or unique name.

**Slice Addressing**
Operation-specific Slice targeting by current index or unique name.

**Tileset Addressing**
Operation-specific Tileset targeting by current index, unique name, or an exactly addressed referencing Tilemap Layer.

### Orchestration and implementation

**Operation Plan**
A bounded ordered list of eligible public Operations applied to one Sprite in one Aseprite process and adapter unit of work.

**Plan Step**
One Operation invocation and its preconditions within an Operation Plan.

**Domain Module**
The vertical code-ownership envelope for Operations that share domain language and reasons to change. It is not a logical layer or Command Group.

**Lua Operation Kernel**
The packaged private handler system that owns core Aseprite creation, editing, inspection, validation, conversion, and export behavior. Standalone and Plan execution use the same handlers.

**Kernel Protocol**
The private versioned request/response transport between Python and the Lua Operation Kernel.

**Aseprite Adapter**
The outbound adapter that owns runtime discovery, resources, process launch, Kernel transport, diagnostics, staging integration, and native observations.

**Agent Skill**
Version-matched guidance that teaches agents how to discover and invoke the installed SPA operation surface.

**SPA MCP Adapter**
An inbound adapter that derives tools from the installed Surface Manifest and invokes the `spa` CLI without owning Operation semantics.

**Anti-Corruption Layer (ACL)**
The downstream-owned translation between Asset Pipeline concepts and the public SPA Published Language.

## Authority index

- ADR-0001: Bounded Context and external relationships.
- ADR-0002: Operation Descriptor authority.
- ADR-0003 through ADR-0005: Operation Plan, validation, and guard phases.
- ADR-0006: operation-specific targets and identity.
- ADR-0007: Core Domain priority and demand-driven supporting work.
- ADR-0008 through ADR-0010: bounds, module ownership, and Lua Kernel authority.
- ADR-0011 through ADR-0016: caller scripts, protocols, results, file semantics, Artifacts, and Asset Pipeline stability.
- ADR-0017: command catalog and artifact ownership.
- Later accepted ADRs: durable Aseprite-aligned geometry, identity, lifecycle, raster, color, Tile, Filter, and export decisions referenced by their owning feature issues.
