# ADR-0072: Separate native Filters from Freehand Paint tools

## Status

Accepted

## Context

Aseprite uses the word and mechanism Filter for a cohesive set of batch image
commands. Its source groups Brightness/Contrast, Hue/Saturation, Color Curve, Replace
Color, Invert Color, Outline, Convolution Matrix, and Despeckle under
`commands/filters`. They share Filter concepts and execution machinery such as target
channels, Selection, Cel/Frame scope, tiled mode, and the Filter manager while keeping
operation-specific parameters.

The editor navigation divides some of these commands between Adjustments and FX and
places Replace Color and Invert Color directly under Edit. Those menu locations do
not change their shared native implementation language.

Aseprite also has a toolbar group internally named effects containing Blur and
Jumble. Unlike batch Filters, both are native Freehand Paint tools with a Brush,
Points, Controller, Ink, and Tool Loop. A universal SPA `effect` category would erase
this functional distinction.

## Decision

- SPA establishes `filter` as the CLI navigation group for Aseprite native Filter
  commands.
- The group belongs to the existing Raster Authoring Domain Module. It is not a new
  bounded context or independent subsystem.
- Initial Command Catalog territory includes `filter brightness-contrast`,
  `filter hue-saturation`, `filter color-curve`, `filter replace-color`,
  `filter invert-color`, `filter outline`, `filter convolution-matrix`, and
  `filter despeckle`.
- Adjustments and FX remain Aseprite-aligned documentation subcategories, not SPA
  top-level groups, modules, or domain boundaries.
- Native Blur and Jumble remain `paint blur` and `paint jumble` because their business
  behavior is an explicit bounded Freehand Brush gesture.
- Every Filter and Paint tool owns an independent Operation Descriptor, Schema, fixed
  Lua Kernel handler, typed result or Capability Gap, and version constraints. Its
  feature issue owns acceptance evidence.
- Shared Filter target, channel, Selection, Cel/Frame scope, tiled-mode, execution,
  and result components can be extracted when concrete vertical slices prove them.
- SPA does not define a generic `effect` group, universal Effect model, Filter DSL,
  arbitrary filter-code entrypoint, arbitrary convolution request, or plug-in system.

## Consequences

- The CLI remains discoverable while preserving Aseprite's behavioral distinction
  between sampled painting and batch filtering.
- Shared Filter machinery can remain DRY without flattening operation-specific
  contracts.
- UI menu organization informs documentation but does not create architecture.
- Filters can deepen independently as functional capabilities without expanding into
  an open-ended image-processing framework.

## Rejected alternatives

### Create one `effect` group

The term would conflate native Freehand tools, Adjustments, FX, and potentially any
future image-processing behavior without a common Aseprite execution contract.

### Put Blur and Jumble under `filter`

Their native Brush gesture, Controller, and Tool Loop semantics belong to Paint.

### Mirror Adjustments and FX as top-level groups

They are editor navigation labels and would fragment one shared Filter mechanism.

### Define one generic Filter request or plug-in protocol

It would weaken strict schemas and create an image-processing extension platform
beyond the accepted Aseprite automation boundary.
