# Aseprite Automation

Aseprite Automation provides a typed automation layer over Aseprite for AI agents and CI. The project name is `aseprite-automation`; its primary executable is `spa`.

> [!IMPORTANT]
> This repository is at the bootstrap stage. The product architecture has been tested through disposable prototypes, but there is no production CLI release yet. [Issue #1](https://github.com/aigengame/aseprite-automation/issues/1) is the current product requirements authority. Shipped behavior will be defined by the installed CLI schemas and verified vertical slices.

## Background

Aseprite exposes useful batch and Lua scripting capabilities, but `aseprite --script` is not an agent-facing automation contract. A direct caller must still construct scripts, encode parameters, separate diagnostics from results, detect failures, protect source files, and verify generated artifacts.

SPA adds that missing product boundary. It turns common sprite workflows into fixed, parameterized operations with strict inputs, structured results, stable failures, and observable postconditions. Ordinary operations use packaged Lua scripts; they do not generate temporary Lua source. Arbitrary Lua remains an explicit trusted escape hatch.

## Product Position

SPA is an **Aseprite automation toolchain for AI agents**. The CLI is the first and authoritative execution channel.

SPA aims to provide a deterministic loop:

```text
discover -> inspect -> create or edit -> verify -> export
```

The product is designed for agents, CI jobs, and asset pipelines that need reproducible sprite operations. It is not an autonomous art director, a replacement for Aseprite's interactive editor, or a guarantee of visual quality.

## Capability Territory

The table describes the intended product territory. A capability is supported only after it ships through a verified vertical slice and appears in the installed aggregate schema.

| Area | Responsibility |
| --- | --- |
| Runtime | Discover and validate an external Aseprite installation, its resources, version, and scripting capabilities. |
| Document and animation | Create and edit sprites, layers, frames, cels, tags, timing, palettes, and color data. |
| Raster authoring | Apply bounded bitmap patches and typed paint operations without expanding work into thousands of per-pixel process calls. |
| Tile authoring | Create and inspect tilemaps and tilesets with stable tile keys, typed transform flags, explicit coordinate spaces, and bounded observations. |
| Other authored objects | Work with selections, slices, text, effects, and related Aseprite concepts when their contracts have verified semantics. |
| Inspection | Return enough typed document facts to select mutation targets and verify results. Missing, ambiguous, unsupported, and omitted facts remain explicit. |
| Validation and comparison | Check structural properties, pixels, metadata, artifacts, and digests. Visual review remains separate from structural proof. |
| Planning | Apply a bounded sequence of existing operations to one sprite document in one Aseprite process and one adapter unit of work. |
| Delivery | Export sprites, animation sheets, GIFs, tilesets, previews, and normalized metadata through a structured artifact manifest. Add conversions only when their semantics are proven. |
| Agent access | Publish version-locked Agent Skill guidance and generate MCP tools from the installed CLI schema without a second command registry. |
| Integration | Act as an Aseprite authoring and export subsystem for external asset pipelines through the public CLI JSON ABI. |

Command groups are a navigation surface, not the module architecture. Inspection and validation stay with the domain concepts that they observe. `plan` is bounded orchestration, delivery operations own export and conversion, and `script run` is the explicitly unsafe extension point.

## Public Contract

The initial Open Host Service is the typed command service exposed by `spa`. Its Published Language is the versioned set of input, output, error, operation metadata, artifact, and aggregate-manifest schemas.

The public contract follows these rules:

- Each command has strict typed input and output schemas.
- JSON output contains only a documented success result or failure envelope.
- Stable error categories do not require callers to match diagnostic prose.
- Human-readable output is derived from the same result models.
- One aggregate manifest describes every dispatchable operation and its effective limits.
- Structured parameters can carry nested objects, arrays, paths, and large payloads without fragile shell encoding.
- Selectors declare cardinality and return the resolved locator that was used.
- Coordinate-bearing fields identify canvas-pixel, tile-cell, or tile-bitmap-pixel space explicitly.
- Results distinguish host-local artifact locators from portable artifact content.

REST and remote HTTP are deferred. A future remote adapter must reuse the same semantics and also define artifact transfer, identity, authorization, concurrency, cancellation, and retention.

## Technical Architecture

SPA uses one **Sprite Automation** bounded context. Domain rules do not depend on Aseprite process details, MCP, Godot, or an external asset pipeline.

```text
AI agents / CI / Asset Pipeline
    |
    +-- spa CLI -----------------------------+
    |                                        |
    +-- spa-mcp -- invokes installed spa ----+--> Typed command service
    |                                        |    and aggregate schema
    +-- spa Agent Skill -- usage guidance ---+
                                             |
                                             v
Application use cases and operation descriptors
    |
Sprite Automation domain model and ports
    |
    +-- Aseprite outbound adapter
    |      |
    |      +-- fixed, packaged Lua operation kernel
    |      +-- versioned request/response codec
    |      +-- process, timeout, and diagnostic handling
    |
    +-- staged file commit and artifact validation
           |
           v
 External Aseprite: --batch --script
```

### Layer responsibilities

- **Contract authority:** typed operation descriptors define registration, schema, help, result rendering, MCP discovery, and Lua handler binding.
- **Application layer:** use cases coordinate domain rules, limits, output intent, and ports. They do not contain Aseprite subprocess mechanics.
- **Domain layer:** models sprite documents, authored objects, selectors, coordinate spaces, mutations, observations, validation rules, and artifacts.
- **Aseprite adapter:** owns executable discovery, platform resources, process execution, the private JSON/Lua boundary, fixed Lua scripts, diagnostics, and Aseprite-specific behavior.
- **File and artifact adapters:** own staged saves, atomic target replacement, digests, output coordination, and artifact verification.
- **MCP adapter:** launches the installed `spa` executable, discovers tools from its aggregate schema, forwards structured inputs, and relays the same results.

## Planned Technology Stack

| Component | Technology and role |
| --- | --- |
| CLI and application | Python 3.13 with Typer for the human and automation command surface. |
| Contracts | Pydantic 2 models as the source for validation, JSON Schema, structured results, and failure envelopes. |
| Project and packaging | `uv` for Python environments, dependencies, builds, and installed-product tests. |
| Aseprite operations | Fixed, versioned Lua scripts executed by an external Aseprite process through `--batch --script`. |
| Private adapter protocol | Versioned JSON request and response files passed by `--script-param`, with process output captured separately as bounded diagnostics. |
| MCP | An optional Python dependency and a thin subprocess adapter generated from the installed aggregate schema. |
| Agent guidance | A version-locked Agent Skill distributed with the CLI and derived from the same supported operation surface. |

This stack is the current decision in the product requirements. A later validated distribution constraint can change it; the public typed contract and domain boundaries must remain independent of the chosen framework.

## Aseprite Execution Model

Aseprite is an external installed dependency. SPA does not bundle the official executable by default. Runtime discovery reports the requested, discovered, and canonical executable paths, verifies required resources, and identifies the exact tested version before mutation.

A normal mutation follows this unit of work:

1. Validate the public request, selectors, limits, output intent, and optional input digest.
2. Resolve a supported, resource-complete Aseprite runtime.
3. Pass validated data to a fixed Lua handler through versioned request and response files referenced by `--script-param`.
4. Create or open the document outside `app.transaction`, then apply supported document edits inside one transaction.
5. Save to a staged path and validate the private response and required artifacts.
6. Atomically replace the declared target only after validation succeeds.
7. Emit a schema-valid public result with effects, phases, warnings, artifacts, and applicable digests.

A successful Aseprite process exit is not sufficient evidence of success. SPA requires a valid private response and the expected file effects. End-to-end tests independently reopen outputs through a real supported Aseprite binary and observe the persisted result.

A bounded operation plan applies only to one sprite document. Cross-document ordering, bundles, installation, retry, and project acceptance belong to the caller or an external asset pipeline.

## Safety and Trust Boundary

The normal environment is a trusted local workspace with a trusted Aseprite installation and packaged SPA operations.

- New output is the safe mutation default; in-place changes require explicit intent.
- Optional digest preconditions and output coordination prevent silent last-write-wins behavior.
- Resource limits use separate units for requests, operations, raster pixels, tile pixels, tile cells, tiles, frames, cels, runtime, diagnostics, responses, and artifacts.
- Packaged ordinary operations preserve unrelated user and plugin metadata.
- `script run` executes arbitrary Lua and is explicitly outside the ordinary-operation safety contract.
- SPA does not claim to sandbox untrusted Lua or provide a remote multi-tenant security boundary.

## Asset Pipeline Boundary

SPA can support `gda asset-pipeline` through an Asset Pipeline-owned anti-corruption adapter that invokes the public `spa` CLI ABI.

- **SPA owns:** Aseprite document and visual-asset semantics, sprite editing, inspection, bounded structural validation, and Aseprite/raster export facts.
- **Asset Pipeline owns:** workflow order, concept and reference handoff, project recipes, produced-file roles, installation, retry, and project acceptance.
- **gda owns:** Godot import facts, engine behavior, and runtime observations.

These systems exchange normalized artifact manifests. They do not import each other's internal models, and a SPA validation result is not Godot runtime evidence.

## Delivery Strategy

The project grows through small, evidence-bearing vertical slices. A high command count or the expressiveness of raw Lua does not prove that SPA covers agent sprite workflows.

The first production tracer will prove the complete installed CLI path with a real Aseprite process: runtime discovery, descriptor-derived schemas, a small multi-frame sprite plan, bounded raster authoring, independent inspection, typed postconditions, failure without target commit, digest conflict refusal, and validated `.aseprite`, sprite-sheet, metadata, and GIF artifacts.

Later slices will expand animation semantics, add the Agent Skill and MCP adapter, integrate with Asset Pipeline, and then add selection, effects, slices, text, and tile capabilities according to measured user value. A maintained workflow corpus will determine coverage claims.

## Non-Goals

- Editor UI automation, a persistent interactive editor session, or full Aseprite feature parity.
- Generated Lua source for ordinary operations.
- An embedded model, autonomous art direction, or automatic aesthetic acceptance.
- A general workflow DAG, background job system, plugin marketplace, or cross-document transaction.
- Godot project semantics, gameplay validation, or asset installation inside SPA.
- Bundling or redistributing Aseprite.
- A REST service before a named remote consumer and its artifact lifecycle are understood.

## Project Documents

- [Product requirements and prototype findings](https://github.com/aigengame/aseprite-automation/issues/1)
- [Aseprite CLI documentation](https://www.aseprite.org/docs/cli/)
- [Aseprite scripting documentation](https://www.aseprite.org/docs/scripting/)
