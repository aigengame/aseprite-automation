# ADR-0089: Define the native Change Color Mode contract

## Status

Accepted

## Context

Aseprite defines Color Mode and the Change Color Mode operation, exposed to scripts
as `ChangePixelFormat`. SPA needs the same behavior both as a Sprite-wide Mutation and
inside `export image` on a disposable export Sprite. One fixed Lua implementation must
serve both callers.

The native scripting command presents a broad parameter object whose effective fields
depend on the source and target Color Modes. It also contains implicit fallbacks that
are unsuitable for an agent contract. An omitted RGB Map Algorithm or Color Best Fit
Criteria for conversion to Indexed reads editor preferences. Their explicitly passed
native `default` values are deterministic choices, while an unknown string is also
silently parsed as `default`. An unknown Dithering value becomes `none`. A missing or
unknown Dithering Matrix falls back to Bayer 8-by-8 after diagnostic output. An
omitted or unknown Grayscale method ultimately uses Luma.

The implementation also proves that Dithering affects RGB-to-Indexed conversion but
is ignored for Grayscale-to-Indexed conversion. Conversion to RGB needs no conversion
options. Conversion to Grayscale needs only the native `toGray` function. Requesting
the current Color Mode returns without mutation.

Aseprite's Change Color Mode dialog can separately offer Merge layers, but that UI
choice is not part of the non-interactive command parameters. Layer flattening and
Color Mode change also have different observable responsibilities and can be composed
explicitly where a Sprite mutation needs both.

## Decision

- **Change Color Mode** is the canonical Aseprite operation term. The earlier generic
  Color Conversion glossary entry is removed; contextual use of the verb conversion
  does not create another domain concept.
- `spa sprite change-color-mode` is an explicit Sprite command. Color Mode is not a
  generic property assignment hidden inside `spa sprite set`.
- `export image` embeds the same typed Change Color Mode request in its
  `color_mode: change` branch and invokes the same fixed Lua Kernel implementation
  against its disposable export Sprite. The `preserve` branch does not invoke it.
- The request is discriminated by target Color Mode and validated against the actual
  source Color Mode:
  - target `rgb` accepts no conversion-specific parameters;
  - target `grayscale` requires `to_gray: luma | hsv | hsl` and accepts no Palette,
    RGB Map Algorithm, Color Best Fit Criteria, or Dithering inputs;
  - target `indexed` uses the Sprite's already established Effective Palettes and
    requires an explicit RGB Map Algorithm and Color Best Fit Criteria using the
    native unions accepted in ADR-0091. RGB source additionally requires an explicit
    Dithering branch, including `none`; Grayscale source rejects Dithering because the
    native path ignores it. Palette preparation remains a separate explicit Palette
    operation as defined by ADR-0090.
- Source and target equality is a valid idempotent no-op. It accepts none of the
  target-specific conversion parameters and returns `changed: false` with the
  observed unchanged Color Mode and content facts.
- Missing required values, unknown strings, numeric enums, target-inapplicable fields,
  source-inapplicable fields, and combinations that Aseprite would ignore or resolve
  from preferences fail before mutation. Explicit documented `default` values remain
  valid native choices, while an invalid value may never reach Aseprite's `default`
  fallback.
- ADR-0091 defines the exact RGB Map Algorithm and Color Best Fit Criteria contracts.
  ADR-0092 defines the conditional Dithering Algorithm, Dithering Matrix, and
  Dithering Factor contract for RGB-to-Indexed conversion. ADR-0090 separately defines
  Current/Effective Palette use and Color Quantization composition.
- Merge layers is not a Change Color Mode request field. A Sprite workflow uses the
  accepted Plan composition with a Layer operation when flattening is intended.
  `export image` already renders its explicit Layer Composition into the disposable
  export Sprite and applies Color Profile before any requested Color Mode change, as
  fixed by ADR-0094.
- As a Sprite Mutation, Change Color Mode applies to the complete Sprite using
  Aseprite's native operation, including every applicable unique Cel Image and
  Tileset Tile Image. It reports source/target Color Mode, all affected Images, Cels,
  Tilesets and Tiles, Palette and Transparent Color Index facts, and persisted
  postconditions. Normal all-or-nothing Target Commit semantics apply.
- As an export step, it changes only the disposable one-Frame export Sprite and
  reports the corresponding source/effective Color Mode and conversion facts. It
  never saves changes to the Source Sprite File.
- Aseprite owns Color Mode conversion, Palette lookup, Grayscale conversion,
  quantization, mapping, Dithering, transparency, and Tile Image behavior. The fixed
  Lua Kernel owns typed native mapping, invocation, observation, and shared behavior.
  Python performs no pixel or Palette conversion.
- Delivery requires a real-runtime matrix covering every source/target pair, same-mode
  no-op, every accepted method, rejected missing/unknown/irrelevant values, Palette
  Changes across Frames, Alpha and Transparent Color Index, Background and transparent
  Layers, linked Cels, Tilemap/Tileset Images, source immutability for export,
  restoration/failure, and save/close/reopen verification.

## Consequences

- SPA uses one native operation vocabulary and one Kernel behavior for editable
  Sprite mutation and disposable export conversion.
- Target-specific schemas prevent ignored fields and preference-dependent fallbacks.
- Dithering cannot be presented as meaningful for a native path that ignores it.
- Layer flattening remains independently composable rather than becoming a hidden
  side effect of Color Mode change.
- Indexed conversion retains its complete native mapping and Dithering choices while
  rejecting combinations the native command ignores or silently replaces.

## Rejected alternatives

### Keep Color Conversion as a parallel domain term

It overlaps Aseprite's Change Color Mode language and encourages a generic conversion
framework rather than the native operation and its exact inputs.

### Use one bag of optional parameters

The native implementation ignores many cross-direction fields and silently resolves
others from preferences or fallback values.

### Reject same-mode requests

Aseprite treats them as no-ops, and an explicit idempotent result is useful for agent
workflows when it carries no irrelevant conversion input.

### Include Merge layers

It is a separate Layer mutation, absent from the non-interactive command parameters,
and explicitly composable through an Operation Plan.

### Implement export conversion separately

That would violate DRY and allow editable-Sprite and export Color Mode behavior to
diverge.
