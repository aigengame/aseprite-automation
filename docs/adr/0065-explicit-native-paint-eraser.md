# ADR-0065: Preserve both native Eraser behaviors explicitly

## Status

Accepted

## Context

Aseprite's Eraser tool is not Pencil painting with a transparent color. Its left
button uses Eraser Ink, while its right button replaces the foreground color with the
background color. Native erasure also differs between transparent Layers and
Background Layers.

For Background erasure, Aseprite obtains the clear color from background-color state
instead of the `bgColor` supplied to `app.useTool`. SPA must control that dependency
without exposing mutable editor state or replacing the native algorithm.

## Decision

- `spa paint eraser` invokes Aseprite's fixed `eraser` tool through Native Tool
  Invocation.
- It reuses Paint Pencil's non-empty ordered Image Pixel `points`, single native
  press/move/release gesture, Standard Paint Brush, integer opacity in `0..255`, and
  explicit `regular`, `pixel-perfect`, or `dots` Freehand Algorithm.
- Point preservation, native path interpretation, actual Brush-footprint bounds,
  explicit clipping, Selection Application, Linked Image, transaction, and
  postcondition rules remain shared with Paint Pencil.
- Paint Eraser accepts no generic Ink and exposes no mouse-button input. A required
  discriminated behavior selects the exact native Ink.
- `erase` selects native left-button Eraser Ink.
  - A transparent Layer accepts no color. RGB and Grayscale use native alpha erasure;
    Indexed uses the Sprite's Transparent Color Index.
  - A Background Layer requires one compatible `background_color`. The fixed Lua
    Kernel sets and restores Aseprite's background-color preference because the
    native erasure path does not consume `app.useTool.bgColor`.
- `replace-foreground-with-background` selects native right-button
  `replace_fg_with_bg` Ink. It requires compatible `foreground_color` and
  `background_color` and replaces matching foreground values only under the native
  Brush gesture.
- Fields belonging to another behavior are rejected rather than ignored.
- Image Brush and Paint Dynamics retain their separate intended functional
  Capability Gaps.
- Issue #27 owns the behavior and Color Mode delivery matrix and real-runtime
  acceptance evidence. Failure yields the specific typed Capability Gap.
- SPA never substitutes Pencil with alpha zero or implements erasure in Python or an
  alternate Lua rasterizer.
- Results return exact Points, behavior, normalized Brush/opacity/algorithm and
  applicable colors, requested and actual native coverage, clipping and Selection
  counts, every affected Cel/link, native transparency or replacement facts, and
  before/after content digest. Save/close/reopen verifies persisted facts.

## Consequences

- Transparent erasure, Background clearing, and foreground replacement remain
  distinct and reproducible native behaviors.
- Agents express semantic intent instead of input-device details.
- Background-color state is bounded to one invocation and cannot leak into another
  request.
- Pencil and Eraser retain independent Aseprite meanings even when some pixels might
  appear similar.

## Rejected alternatives

### Use Pencil with a transparent color

It does not reproduce native Eraser Ink across opacity, Indexed, and Background
semantics.

### Expose left and right mouse buttons

Buttons are an editor input mechanism; the two result-bearing Eraser behaviors are
the agent-facing intent.

### Accept a generic Ink field

The selected Eraser behavior already determines the exact native Ink.

### Read the active background color

Identical Background-erasure requests would produce different pixels.
