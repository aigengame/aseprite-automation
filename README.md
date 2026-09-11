# Aseprite Automation

Aseprite Automation provides agent-facing automation for Aseprite. The project name is `aseprite-automation`; its primary executable is `spa`.

> [!IMPORTANT]
> This repository is at the bootstrap stage. The product architecture has been tested through disposable prototypes, but there is no production CLI release yet. [Issue #1](https://github.com/aigengame/aseprite-automation/issues/1) is the umbrella PRD; milestones and feature issues own delivery contracts and evidence. `CONTEXT.md` and accepted ADRs own the aligned language and durable decisions. Shipped behavior will be defined by the installed CLI schemas.

## Background

Aseprite exposes useful batch and Lua scripting capabilities, but `aseprite --script` is not an agent-facing automation contract. A direct caller must still construct scripts, encode parameters, separate diagnostics from results, detect semantic failures, protect source files, and verify generated artifacts.

SPA adds that product boundary. It turns sprite workflows into parameterized Operations with typed inputs, structured results, stable failures, and observable postconditions. Ordinary Operations use packaged Lua handlers; they do not generate temporary Lua implementations. Caller-owned Lua remains the explicit `script run` escape hatch.

## Product Position

SPA is an **Aseprite automation toolchain for AI agents**. Its business capability is equivalent to Aseprite's: it provides agent-facing mechanisms for sprite creation, editing, inspection, validation, conversion, and export, and develops these functional capabilities broadly and deeply for agent use.

SPA provides a structured and verifiable loop:

```text
discover -> inspect -> create or edit -> verify -> export
```

The product serves agents, CI jobs, and asset pipelines that need explicit sprite operations and inspectable evidence. It preserves and observes native Aseprite behavior, including declared stochastic behavior. SPA does not take ownership of gameplay, engine integration, art direction, or another product domain.

## Capability Territory

The table describes intended territory. A capability is supported after an evidence-bearing vertical slice ships and appears in the installed Surface Manifest.

| Area | Responsibility |
| --- | --- |
| Runtime | Discover an external Aseprite installation, resources, version, scripting capabilities, and evidence-backed Capability Gaps. |
| Document and animation | Create and edit Sprites, Layers, Frames, Cels, Tags, timing, Palettes, and color data. |
| Raster authoring | Inspect and transform Images; apply bounded Pixel Patches, native Paint operations, and native Filters. |
| Tile authoring | Create and inspect Tilemaps and Tilesets with stable Tile Keys, typed flags, explicit Coordinate Spaces, and bounded results. |
| Other authored objects | Work with Selections, Slices, text, and related Aseprite concepts through verified contracts. |
| Inspection and validation | Return the facts needed to select targets, verify persisted results, and report structural findings. |
| Planning | Apply a bounded sequence of existing Operations to one Sprite in one Aseprite process and adapter unit of work. |
| Delivery | Export raster, animation, sheet, Tileset, preview, and metadata Artifacts with independent verification. |
| Agent access | Publish version-locked Agent Skill guidance and project the installed operation surface through MCP. |
| Integration | Participate in external asset workflows through the public CLI JSON ABI. |

Command Groups are navigation, not module architecture. Domain Modules own cohesive vertical slices and can project several groups when native behavior shares a lifecycle. `image` represents Aseprite Image observation and structural transformation; `paint` represents authoring intent. Native batch Filters remain distinct from native Paint tools. The [command catalog](docs/command-catalog.md) lists candidate territory; feature issues own delivery contracts.

## Public Contract

The CLI is the first Open Host Service. Its Published Language is the versioned set of request, Operation Result, Failure Envelope, Operation metadata, Artifact, and Surface Manifest schemas. Human output, MCP tools, and the private Python/Lua transport are projections rather than independent contracts.

- Each Operation has strict typed request, result, and failure schemas.
- Machine output contains a schema-valid Operation Result or Failure Envelope and stays separate from vendor diagnostics.
- Stable Failure Codes drive automation; typed Failure Details and human Diagnostics have different roles.
- The Surface Manifest describes every callable Operation, side effects, determinism, version constraints, and schemas.
- Each Operation defines Aseprite-aligned target fields, cardinality, Inspection Scope, Domain Bounds, and result facts. SPA has no universal Selector or Locator.
- Inspections report normalized coverage and completeness. Native absence, not requested, unsupported, and exceeded bounds remain distinct.
- Coordinate-bearing requests name their Coordinate Space. Public Rectangles use Aseprite's `x`, `y`, `width`, and `height` vocabulary and half-open coverage.
- Color Values preserve RGB, Grayscale, Indexed, Alpha Channel, Transparent Color Index, Palette, sRGB, and ICC distinctions from Aseprite.
- Ordinary multi-target Mutations resolve the complete target set and produce a Target Commit for the whole set or none of it.
- Every produced file is a verified Artifact in the owning Operation Result. Format-specific facts stay with that result.
- Operation Descriptors own registration and projections. The Lua Operation Kernel owns core Aseprite behavior. Python coordinates use cases and adapters without duplicating that behavior.
- Capability Gaps are versioned, evidence-backed runtime facts. They remove unfaithful Operations from the installed Surface Manifest instead of creating silent partial support.

Exact feature contracts belong to their accepted issue and referenced ADRs. The installed Surface Manifest becomes the authority after a feature ships.

## Technical Architecture

SPA uses one **Sprite Automation** Bounded Context. Domain rules do not depend on Aseprite process details, MCP, Godot, or an external asset pipeline.

```text
AI agents / CI / Asset Pipeline
    |
    +-- spa CLI -----------------------------+
    |                                        |
    +-- spa-mcp -- invokes installed spa ----+--> Published Language
    |                                        |    and Surface Manifest
    +-- spa Agent Skill -- usage guidance ---+
                                             |
                                             v
Application use cases and Operation Descriptors
    |
Sprite Automation domain model and ports
    |
    +-- Aseprite outbound adapter
    |      +-- packaged Lua Operation Kernel
    |      +-- versioned request/response codec
    |      +-- process and diagnostics handling
    |
    +-- staged Target Commit and Artifact verification
           |
           v
 External Aseprite: --batch --script
```

### Subdomain priorities

Sprite Automation is the Core Domain and receives the highest delivery priority. It includes Aseprite-equivalent sprite capabilities plus the agent-facing control, composition, observation, and verification that make them usable. Runtime integration, access projection, and Asset Pipeline integration support the Core Domain. Domain-neutral framework and utility code is Generic. Supporting and Generic work follows accepted Core Domain requirements, uses proportionate abstraction, and does not establish an independent roadmap. [ADR-0007](docs/adr/0007-demand-driven-nfrs.md) owns this boundary.

### Responsibilities and dependencies

- **Operation Descriptors:** own public registration, schema, execution metadata, rendering projection, MCP discovery, and Lua handler binding.
- **Application layer:** coordinates domain rules, packaged Kernel capabilities, Aseprite invocations, staging, results, and Artifact publication.
- **Domain Modules:** own cohesive vertical feature slices across contract, domain, application, presentation, and Lua binding responsibilities.
- **Lua Operation Kernel:** owns creation, editing, observation, validation, conversion, and export behavior executed against Aseprite. Standalone and Plan paths use the same handlers.
- **Aseprite adapter:** owns runtime discovery, resources, process execution, the private protocol, fixed scripts, diagnostics, and native integration facts.
- **File and Artifact adapters:** own staging, Target Commit, Export Destination mapping, digests, and independent output checks.
- **MCP adapter:** discovers the installed Surface Manifest, invokes `spa`, and relays equivalent requests and results.

Inbound adapters depend on Application and Domain contracts. Concrete outbound adapters depend on inner-owned ports. Bootstrap composition binds concrete adapters and entry points. Application use cases coordinate cross-module behavior without cyclic dependencies or shared mutable state.

## Planned Technology Stack

| Component | Technology and role |
| --- | --- |
| CLI and application | Python 3.13 and Typer for human and structured command access. |
| Contracts | Pydantic 2 models for validation, JSON Schema, structured results, and Failure Envelopes. |
| Project and packaging | `uv` for environments, dependencies, builds, and installed-product tests. |
| Aseprite operations | Fixed versioned Lua handlers executed by external Aseprite through `--batch --script`. |
| Private transport | Versioned JSON request/response files passed by `--script-param`, with bounded diagnostics captured separately. |
| MCP | Optional thin subprocess adapter derived from the installed Surface Manifest. |
| Agent guidance | Version-locked SPA Skill distributed with the CLI. |

This stack can change after validated distribution evidence. The public contract and domain boundaries remain independent of the selected framework.

## Aseprite Execution Model

Aseprite is an external installed dependency. Runtime discovery reports requested, discovered, canonical, and resource-complete executable facts before mutation.

A normal mutation performs these steps:

1. Validate the public request, Source/Target or In-place intent, paths, Operation eligibility, and Domain Bounds.
2. Resolve a supported Aseprite runtime.
3. Pass validated data to packaged Lua handlers through the versioned private protocol.
4. Create or open the Sprite, resolve the complete target set, and perform eligible edits inside native transaction boundaries.
5. Evaluate Postconditions, save to a Staged Sprite File, and validate the private response and staged file.
6. Commit the staged file to the declared Target after validation succeeds.
7. Emit a schema-valid Operation Result, or a Failure Envelope with a non-zero SPA exit.

Process exit alone is not completion evidence. End-to-end tests independently reopen or decode outputs. An Operation Plan remains single-Sprite; cross-document composition belongs to its caller or an external asset pipeline.

## Trust Boundary

The operating model is a trusted local workspace with a trusted Aseprite installation and packaged SPA Operations.

- Source, Target, In-place intent, staging, overwrite behavior, and Export Destinations are explicit.
- Domain Bounds use units meaningful to each Operation. Process timeout and captured-output bounds remain adapter Execution Guards.
- Packaged Operations preserve unrelated user and plug-in metadata.
- `script run` executes caller-owned Lua outside the ordinary Operation behavior contract.
- SPA does not add authentication, authorization, audit history, distributed consistency, service governance, or a remote multi-tenant boundary to the local tool.

## Asset Pipeline Boundary

SPA is committed to integration with the developing gda Asset Pipeline through an Asset Pipeline-owned Anti-Corruption Layer that invokes the public SPA JSON ABI. The pipeline is under validation, so its current command names and tactical abstractions do not become SPA contracts.

- **SPA owns:** Aseprite document and visual-asset semantics, editing, inspection, validation, and export facts.
- **Asset Pipeline owns:** workflow order, concept/reference handoff, recipes, produced-file roles, installation, retry, and project acceptance.
- **gda owns:** Godot import, engine, and runtime evidence.

## Delivery Plan

The project grows through evidence-bearing vertical slices. GitHub issues own scope, acceptance, dependencies, and delivery status. Milestones group outcomes and do not imply dependencies that are absent from issue bodies.

- [Phase 1 — Installed CLI Tracer](https://github.com/aigengame/aseprite-automation/milestone/3): issues #3–#7
- [Phase 2 — Sprite and Animation Authoring](https://github.com/aigengame/aseprite-automation/milestone/1): issues #8–#19
- [Phase 3 — Raster and Paint Authoring](https://github.com/aigengame/aseprite-automation/milestone/2): issues #20–#29
- [Phase 4 — Color, Palette, and Filters](https://github.com/aigengame/aseprite-automation/milestone/6): issues #30–#39
- [Phase 5 — Slice, Tile, and Imported Content](https://github.com/aigengame/aseprite-automation/milestone/7): issues #40–#47
- [Phase 6 — Delivery and Agent Access](https://github.com/aigengame/aseprite-automation/milestone/5): issues #48–#55
- [Phase 7 — Asset Pipeline Integration](https://github.com/aigengame/aseprite-automation/milestone/4): issues #56–#57

## Non-Goals

- Editor GUI automation or a persistent interactive editor session.
- Generated Lua implementations for ordinary Operations.
- An embedded model, autonomous art direction, or automatic aesthetic acceptance.
- A general workflow DAG, background job system, plug-in marketplace, or cross-document transaction.
- Godot project semantics, gameplay validation, or asset installation inside SPA.
- Bundling or redistributing Aseprite.
- REST service infrastructure before a named remote consumer and artifact lifecycle require it.

## Project Documents

- [Umbrella PRD and prototype conclusions](https://github.com/aigengame/aseprite-automation/issues/1)
- [Ubiquitous Language and context model](CONTEXT.md)
- [Accepted architecture decisions](docs/adr/)
- [Incremental command catalog](docs/command-catalog.md)
- [Aseprite CLI documentation](https://www.aseprite.org/docs/cli/)
- [Aseprite scripting documentation](https://www.aseprite.org/docs/scripting/)
