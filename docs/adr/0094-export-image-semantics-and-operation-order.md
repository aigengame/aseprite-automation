# ADR-0094: Define Export Image semantics and operation order

## Status

Accepted

## Consolidates

- ADR-0086: Export Image Area versus Selection Mask
- ADR-0087: Export Image Frame and Layer Composition

Issue #7 owns the initial PNG preserve tracer. Issue #59 owns the expanded Export Image
Area, Layer Composition, color, Color Profile, Background, and PNG capability matrix.
Their shared Operation Descriptor owns the implemented request variants and result
fields. Each issue owns planned acceptance, evidence requirements, provenance links,
and curated evidence summaries. Tests and evidence artifacts own executed assertions
and results.

## Context

`export image` creates one static raster Artifact from a selected part of one Sprite
Frame. It must distinguish rectangular rendering from Selection Mask application, use
Aseprite's native Layer compositor, and compose several non-commutative native color
operations on disposable state.

Ambient active Frame, selected Layer, timeline Range, and Selection state cannot define
a typed agent request. Letting the encoder or caller choose the transformation order can
also change the requested colors, Palette, Color Profile, and transparency behavior.

## Decision

- `export image` addresses exactly one explicit Frame and produces exactly one static
  raster Artifact. Frame Ranges, Tags, playback, and multi-image output belong to the
  distinct Sheet, GIF, and Sequence Export Operations.
- Export Image Area is an explicit Canvas Rectangle, optionally resolved from a Slice
  Key. It is not a Selection Mask. SPA never describes a bounding Rectangle as masked
  export or applies a Selection Mask in Python.
- Layer Composition is explicit and uses the accepted Layer addressing rules. It does
  not inherit the active or selected Layer, CLI glob state, or `app.range`.
- The Lua Kernel resolves the effective native Layer set, applies only the temporary
  visibility changes needed by that composition, invokes Aseprite's renderer, and
  restores every changed value on success and handled failure. Aseprite remains the
  authority for stacking, Groups, Blend Modes, opacity, Background, Tilemap, Reference
  Layer, Palette, and pixel rendering.
- The Operation renders the requested Frame, Layer Composition, and Export Image Area
  into one disposable Sprite, then executes these functional steps in order:
  1. apply the declared Color Profile behavior;
  2. prepare a Palette when an explicit Change Color Mode to Indexed requires it;
  3. apply the declared Change Color Mode behavior;
  4. apply the declared transparency or Background behavior; and
  5. invoke the declared File Format encoder.
- Later steps operate only on the rendered disposable Sprite. Color Profile conversion
  precedes quantization and mapping; Background Color is interpreted in the final Color
  Mode and effective Color Profile; the encoder performs no undeclared conversion.
- This sequence is private application-use-case orchestration. Python can select and
  order packaged Kernel capabilities, while each native step remains authoritative in
  Lua. The caller receives semantic choices, not a configurable workflow, Plan, stage
  registry, or intermediate Artifact model.
- Any failure prevents publication, exposes no intermediate file or Sprite, and leaves
  the Source Sprite unchanged. Final publication follows ADR-0085.

## Consequences

- A still-image request has stable output cardinality and no dependency on editor
  selection state.
- Rectangle crop and true masked raster behavior cannot be confused.
- Native Layer composition and color processing retain Aseprite semantics while their
  effective inputs and order are explicit to the agent.
- Sheet, GIF, and Sequence exports can define their own multi-Frame behavior without
  inheriting this still-image contract.

## Rejected alternatives

### Treat Selection bounds as Selection export

Aseprite's bounds export crops a Rectangle and does not apply the non-rectangular Mask.

### Render or composite Layers in Python

That would duplicate Aseprite's native stack, Group, Blend Mode, opacity, Background,
Tilemap, Reference Layer, Palette, and color behavior.

### Let the caller or encoder choose the operation order

It creates invalid permutations and preference-dependent conversions, and makes the
same semantic request produce different output.

### Model internal steps as an Operation Plan

The disposable Sprite is private, Export Operations are not Plan Steps, and callers do
not need access to intermediate state.
