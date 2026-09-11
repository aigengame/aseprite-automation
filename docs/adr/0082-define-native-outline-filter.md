# ADR-0082: Define native Outline Filter

## Status

Accepted

## Context

Aseprite exposes Outline as a native pixel Filter. Its scripting command accepts
placement, an Outline Matrix, outline and background colors, Filter Channels, and
Tiled Mode. The editor also lets a user toggle cells in a 3-by-3 Outline Matrix,
whereas the public command documentation names the common Circle, Square,
Horizontal, and Vertical presets.

The native command has result-affecting ambient defaults that an agent-facing
contract cannot inherit. An omitted outline color can come from editor state, an
omitted Background Color can be derived from the first pixel of a Background Layer,
and invalid strings silently fall back to Outside, no Tiling, or an empty Matrix.

The native algorithm classifies each candidate pixel against an explicit Background
Color, inspects enabled neighboring positions, and writes selected color components
when the requested Inside or Outside predicate matches. The Matrix center bit is
inert: a candidate cannot simultaneously have the opposite background/foreground
classification required for its own center to trigger the predicate.

Aseprite 1.3.18.5 has two Indexed branches. Stored-Index Channels correctly treat
the two colors as Palette Indexes. The component branch first converts the requested
Color to a Palette Index and then reads that integer as though it were packed RGBA.
A real headless probe against a 5-by-5 Indexed Sprite confirmed the consequence: the
Index branch produced the expected four-pixel cross around the source pixel, while
RGBA and Red-plus-Alpha component requests produced no outline. The same probe
confirmed that numeric custom Matrix values reach the native path, that value 1
places the result at the southeast Canvas position relative to the source pixel,
value 256 places it northwest, and the center-only value 16 has no effect.

## Decision

- `spa filter outline` is a deterministic pixel Filter Operation that delegates to
  Aseprite's native Outline command through one fixed Lua Kernel handler. It is
  distinct from Paint Shape outline style.
- The request requires `place` as `inside` or `outside`, an `outline_color`, a
  `background_color`, typed Filter Channels, Filter Cels Target, and Tiled Mode as
  `none`, `x`, `y`, or `both`. It accepts explicit pixel Selection Application.
- Background Color is an Outline classification input. RGB and Grayscale classify a
  pixel as background when it has zero Alpha or exactly equals the declared value.
  Indexed stored-Index execution classifies it by exact Palette Index equality.
- The request requires one typed Outline Matrix:
  - `preset` accepts `none`, `circle`, `square`, `horizontal`, or `vertical`;
  - `custom` accepts a non-empty unique set drawn from `top-left`, `top`,
    `top-right`, `left`, `right`, `bottom-left`, `bottom`, and `bottom-right`.
- Custom positions name the neighboring Image Pixel positions inspected around each
  candidate pixel. The fixed Lua Kernel maps them to Aseprite's native 3-by-3 bits.
  The public contract exposes neither a raw integer mask nor the inert center bit.
  An empty custom set is represented canonically by the `none` preset.
- RGB accepts compatible RGBA Color Values and non-empty component Channels.
  Grayscale accepts compatible Grayscale Color Values and non-empty component
  Channels. Selected components come from the outline color and unselected
  components retain the candidate pixel's values under native behavior.
- Indexed stored-Index execution requires `palette_frame_number`, exclusive `index`
  Channels, and valid Palette Index Color Values for both colors in that Effective
  Palette. Aseprite remains authoritative for the resulting stored values.
- On Aseprite 1.3.18.5, Indexed component Channels report a version-specific native
  Capability Gap. SPA does not reinterpret the converted Index as RGBA, switch to
  Index Channels, pre-render pixels, or implement a replacement outline algorithm.
  A later supported runtime can expose the combination after a real parity gate.
- The Operation has no Filter Application field and never mutates Palette Entries.
  It accepts no thickness, radius, distance metric, blend mode, generic convolution,
  arbitrary Matrix dimensions, or caller-defined code. Repeated native Outline
  Operations can be composed explicitly in an Operation Plan.
- Filter target eligibility, Background Alpha, Linked Image, all-or-nothing mutation,
  state restoration, and persistence rules apply. A shared Image is filtered once
  and every affected Cel is reported.
- Aseprite owns candidate classification, Inside/Outside behavior, neighborhood
  traversal, edge wrapping, component projection, Cel expansion or shrink behavior,
  and Indexed writes. Lua owns validation, typed-to-native mapping, invocation,
  restoration, observation, and the structured result; Python cannot create an
  alternate temporary Lua implementation.
- Results report placement, the canonical Matrix and resolved native representation,
  both colors, effective Channels and Palette basis, Tiled Mode, target/Selection
  facts, unique Images and all affected Cels, candidate/matched/changed counts,
  resulting bounds, and persisted before/after content.
- Delivery requires real-runtime parity for every preset and asymmetric custom
  Matrix, Inside/Outside, all Tiled Modes and edges, supported component and Index
  combinations, transparent/background classification, Selection, Background and
  linked targets, no-op Matrix, rollback, restoration, and save/reopen verification.

## Consequences

- Agents receive the editor's preset and custom Outline capabilities through a typed,
  inspectable contract without depending on mutable editor colors or preferences.
- The custom Matrix is operation-specific functional input, not a generic filter DSL.
- The Indexed component defect remains visible as runtime capability evidence while
  the working native Indexed Index behavior remains available.
- Multiple Outline passes are explicit Plan composition instead of a second
  thickness algorithm.

## Rejected alternatives

### Expose Aseprite's raw Matrix integer

That would leak bit ordering into the Published Language, admit inert or undefined
bits, and make agent requests difficult to validate and explain.

### Expose presets and omit custom Matrix behavior

The editor already provides operation-specific custom neighborhood control. Typed
neighbor positions preserve that functional capability without creating a generic
matrix subsystem.

### Expose the Matrix center as a normal position

Source inspection and a real center-only probe show that it cannot trigger either
native placement predicate. Treating it as effective input would create false
semantics.

### Inherit omitted colors, placement, Matrix, or Tiled Mode

Those defaults can depend on editor state, document state, layer content, or silent
native fallback and therefore do not form a reproducible agent request.

### Reimplement Indexed component Outline

That would create a second raster algorithm and conceal a native capability gap.

### Add a thickness or radius parameter

Aseprite's native command performs one 3-by-3 neighborhood pass. A thickness field
would need semantics that the command does not own; explicit Plan Steps already
compose repeated passes when desired.
