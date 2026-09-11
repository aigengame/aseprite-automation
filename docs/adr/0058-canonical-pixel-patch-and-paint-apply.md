# ADR-0058: Use a canonical Pixel Patch for exact Paint application

## Status

Accepted

## Context

Pixel Region Snapshot represents complete bounded Raster state. Agent editing also
needs a sparse value where omissions mean unchanged rather than a hidden fill.

Aseprite `Image:drawImage` combines placement, implicit clipping, opacity, BlendMode,
and Palette selection. In 1.3.18.5 it clamps opacity and the Cel-associated path uses
Palette 0. Those behaviors must not silently define an exact stored-pixel patch.

## Decision

- Pixel Patch is the canonical sparse Raster mutation value. It declares one positive
  half-open Rectangle in Image Pixel space, matching `color_mode`, and zero or more
  runs.
- Each run has absolute Image Pixel `x/y`, positive `length`, and one compatible Color
  Value. Runs are ordered by `y` then `x`, contained by the declared Rectangle,
  non-overlapping, and merged where adjacent values are equal.
- Listed pixels receive exact stored values. Omitted pixels remain unchanged. An empty
  run list is an explicit, reportable no-op.
- Inline JSON and JSON Artifact inputs use the same schema.
- `spa paint apply` targets an existing Cel on an ordinary Image or Background Layer.
- `clipping` defaults to `reject`, which requires the declared Rectangle inside Image
  bounds. Explicit `clip` intersects runs with Image bounds and reports skipped
  segments. A fully clipped result is a valid no-op.
- The request may carry an explicit Selection Application. The Kernel maps each Image
  Pixel to Canvas Pixel through the addressed Cel position and intersects writes with
  the Selection. Omitted Selection means unrestricted; Empty Selection is a reported
  no-op. Current editor Selection state is ignored.
- The addressed Cel defines Selection mapping. A linked Image is mutated once, and all
  sharing Cels retain the link and observe the change at their own positions.
- The Patch Color Mode must match the target. Every Indexed Palette Index must exist
  in every affected Cel Frame's Effective Palette. Different rendered colors across
  Palette Changes remain native behavior and are reported.
- A Background write must preserve its native opaque postcondition for the target
  Color Mode.
- Reference Cels are rejected because their floating-point bounds need distinct
  pixel-to-Canvas semantics. Tilemap, absent, and non-Cel targets also fail.
- Patch validation and writes execute as one all-or-nothing Mutation.
- Results return input form, requested and applied Rectangle/runs, pixels written or
  skipped by bounds and Selection, relevant Palette facts, every affected Cel/link,
  unchanged geometry, and before/after content digest. Save/close/reopen verifies the
  persisted result.
- Descriptor schemas validate transport shape. The fixed Lua Kernel owns semantic
  normalization, clipping, Selection intersection, Palette applicability, and pixel
  writing. Python does not generate or own an alternate patch implementation.
- `paint apply` performs exact stored-value replacement. Opacity, BlendMode, and Color
  Conversion belong to the distinct candidate `paint composite`.

## Consequences

- Snapshot and Patch encode complete state and sparse change without ambiguity.
- Agents can make compact exact pixel edits and verify every skipped write.
- Explicit Selection remains a request value instead of hidden editor state.
- Native compositing complexity does not weaken exact Patch semantics.

## Rejected alternatives

### Use Pixel Region Snapshot with an omitted-pixel convention

That would give one supposedly complete value two incompatible meanings.

### Implement Patch through `Image:drawImage`

Its clipping, opacity, BlendMode, and Palette behavior do not express direct stored
value replacement.

### Apply current editor Selection

It is hidden state and does not persist through the supported lifecycle.

### Break Linked Cels before writing

Raster mutations preserve native sharing; isolation is explicit through `cel unlink`.
