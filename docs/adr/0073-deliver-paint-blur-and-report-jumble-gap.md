# ADR-0073: Deliver native Paint Blur and report the Jumble velocity gap

## Status

Accepted

## Context

Aseprite groups Blur and Jumble together as native effect Paint tools. Both use a
Freehand Controller, Brush Point Shape, line intertwiner, accumulate trace policy,
opacity, and neighboring source pixels. They are not batch Filters.

Blur Ink deterministically averages a 3-by-3 source neighborhood, maps the result for
the current Color Mode, and blends it through opacity. Jumble Ink randomly selects a
neighboring source pixel and offsets that lookup by native Pointer velocity divided by
four. Both use document Tiled Mode for edge wrapping.

Aseprite 1.3.18.5 `app.useTool` accepts Brush, Points, opacity, and Freehand Algorithm,
but it constructs every Pointer with a fixed zero velocity. It also reads Tiled Mode
from document state rather than a direct call argument. Aseprite exposes native Tiled
Mode control, so a fixed Kernel handler can set and restore it subject to a real state-
restoration gate.

A real discovery probe found that Blur changed 133 pixels and repeated with zero pixel
difference. Jumble changed 105 pixels, and two identical calls differed at 98 pixels.
The latter proves native stochastic execution but does not restore the missing velocity
input.

A separate state probe read the document Tiled Mode as `none`, changed it to `x`
through Aseprite's native scripting command, and restored it to `none`. This proves the
basic control seam but not restoration across every production failure path.

## Decision

- `spa paint blur` declares `deterministic` Operation Determinism and invokes only the
  native `blur` tool and Blur Ink.
- It accepts one non-empty ordered Image Pixel Point sequence as one Freehand gesture,
  Standard Paint Brush, opacity in `0..255`, `regular` or `pixel-perfect` Freehand
  Algorithm, and Tiled Mode `none`, `x`, `y`, or `both`.
- It accepts no Color Value, caller-selected Ink, mouse button, `dots`, random seed, or
  generic convolution input.
- Native Blur remains authoritative for the 3-by-3 neighborhood, one-pixel source
  expansion, interpolation, Brush coverage, opacity blend, Color Mode mapping, and
  edge wrapping.
- The fixed Lua Kernel sets and restores the requested document Tiled Mode around the
  invocation. Shipping requires a real state-restoration and option-independence gate.
- Existing target, bounds, clipping, Selection Application, Background, Linked Image,
  transaction, persistence, and structured-result rules apply.
- Indexed results include the addressed Frame's Effective Palette facts.
- Paint Blur's discovery probe supports reachability and determinism but does not
  replace its complete production editor-parity gate.
- `spa paint jumble` remains an intended `native-stochastic` Aseprite capability.
- On Aseprite 1.3.18.5 it is absent from the Surface Manifest because the scripting
  path cannot provide native Pointer velocity or direction. `spa info` reports a typed
  Pointer Velocity Capability Gap with source and probe evidence.
- SPA does not publish a fixed-zero Jumble subset, infer velocity from Point distance
  or timing, substitute Blur, or implement random displacement in Lua or Python.
- Paint Jumble can ship when a supported native route exposes the relevant Pointer
  behavior and passes stochastic delegation, invariant, actual-result, Tiled Mode,
  state-restoration, target, and persistence gates.

## Consequences

- A useful deterministic native Paint effect can advance without weakening Jumble's
  product contract.
- Tiled edge behavior is explicit and repeatable rather than inherited from editor
  state.
- Native stochastic behavior remains supported and observable without promising exact
  replay.
- A partial scripted result is not mislabeled as editor-equivalent Jumble.

## Rejected alternatives

### Ship Jumble with fixed zero velocity

That would omit a core input used by the native editor behavior and repeat the rejected
fixed-default partial-command pattern.

### Derive velocity from successive Points

The Aseprite scripting boundary still constructs zero-velocity Pointers; an inferred
value would not reach the native Jumble algorithm.

### Implement either effect as a custom image algorithm

That would create a second Blur or Jumble authority and violate the fixed Lua Kernel's
native-operation boundary.

### Move both operations into `filter`

Their Freehand Controller, Brush gesture, and Tool Loop semantics are Paint behavior.
