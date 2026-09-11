# ADR-0018: Keep Image, Paint, and Filter semantics cohesive and distinct

- Status: Accepted
- Date: 2026-09-10

This decision consolidates ADR-0019, ADR-0068, and ADR-0072.

## Context

Aseprite distinguishes structural Image operations, gesture-driven Paint tools, and
batch Filters. They operate on the same raster data and share color, mask, coordinate,
target, linked-Image, and native execution concerns. Treating them as one generic
effect would erase native intent, while separate subsystems would duplicate the same
pixel authority.

## Decision

One Raster Authoring Domain Module owns three public navigation families:

- `image` owns Image observation, replacement, sizing, cropping, and exact structural
  transforms;
- `paint` owns agent-facing raster authoring intent and native Brush-, Ink-, and
  controller-driven operations; and
- `filter` owns Aseprite's native batch Filter operations.

The module owns one set of pixel, Color Value, mask, coordinate, target-resolution,
mutation, and verification semantics. Each materially different native operation keeps
its own Operation Descriptor and packaged Lua handler. SPA does not create a generic
effect model, Filter DSL, plug-in protocol, or second raster algorithm authority.

Blur and Jumble remain Paint operations because they use native Freehand Brush
gestures. Native batch adjustments and effects remain Filter operations regardless of
their editor menu location. Curve, Polygon, and Contour remain distinct Paint
operations because their controllers, completion, and fill behavior differ. Shared
geometry values do not create a universal Path, Segment, or Vector Shape model, and one
operation's Capability Gap does not suppress independently usable native operations.

Raster mutation preserves Aseprite's linked-Cel sharing. Target resolution applies a
mutation once per unique shared Image and reports the complete affected Cel scope,
including linked Cels outside the caller's initial target set. SPA never implicitly
unlinks a Cel; isolated editing uses the explicit native unlink operation.

## Consequences

Public navigation preserves Aseprite's behavioral distinctions while the implementation
keeps shared raster semantics DRY. Native capabilities can deepen independently without
creating parallel pixel models or an open-ended image-processing platform.
