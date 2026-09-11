# ADR-0077: Define native Brightness/Contrast Filter

## Status

Accepted

## Context

Aseprite exposes Brightness/Contrast as a native Filter command. Its editor presents
integer Brightness and Contrast sliders from -100 through 100, and the official
scripting documentation describes integer command parameters in that range. The
native command converts those percentages to internal values and owns the component
mapping, operation order, clamping, and final integer conversion.

The implementation can encode Red, Green, Blue, Gray, and Alpha flags through the
shared Filter target mask, but Brightness/Contrast changes only RGB components or the
Grayscale value. It does not modify Alpha and has no Index-channel operation. Exposing
those encodable flags would create accepted no-op inputs.

Brightness/Contrast is one of Aseprite's two `FilterWithPalette` implementations, so
the explicit Filter Application branches accepted in ADR-0076 apply. Indexed pixel
processing transforms colors through the declared Palette and maps the result back
through Aseprite's RGB Map; Palette applications change RGB values in Palette Entries
while preserving Alpha.

The native Filter window has no Tiled Mode control. Aseprite also exposes no separate
gamma, pivot, curve, or alternate formula as part of this command.

## Decision

- `spa filter brightness-contrast` is a deterministic Filter Operation that delegates
  to Aseprite's native Brightness/Contrast command through one fixed Lua Kernel
  handler.
- The request requires integer `brightness` and `contrast`, each in the inclusive
  range `-100..100`. SPA rejects missing, fractional, non-finite, and out-of-range
  values rather than relying on native coercion or extrapolation.
- An explicit `brightness: 0` and `contrast: 0` is a valid, reportable no-op. SPA does
  not invent a policy error for the native identity setting.
- Brightness/Contrast uses the Filter Application contract from ADR-0076:
  - RGB, Grayscale, and Indexed `pixels`;
  - Indexed `indexed-palette-entries`; and
  - RGB `rgb-palette-colors`.
- Its Filter Channels are limited to a non-empty `components` set that the native
  implementation actually changes:
  - RGB and Indexed component interpretation: any non-empty subset of `red`, `green`,
    and `blue`;
  - Grayscale: `gray`.
- `alpha` and `index` are invalid for every Brightness/Contrast application. Palette
  Alpha and pixel Alpha remain unchanged.
- Existing Filter Cels Target, Selection Application, Palette basis/change, Palette
  Entry, Background, Linked Image, and all-or-nothing rules apply according to the
  selected Filter Application.
- The request accepts no Tiled Mode, custom transfer curve, formula, gamma, pivot,
  alternate color space, or implementation-tuning option.
- Aseprite's native percentage conversion, contrast-before-brightness computation,
  component map, clamping, quantization, Palette matching, and RGB Map behavior are
  Core Operation Semantics owned by the fixed Lua Kernel invocation. Python and Lua
  code do not reproduce the arithmetic as an alternate implementation.
- The Operation Result reports the accepted percentages, effective Channels and
  Filter Application, resolved target and Palette facts, changed Palette Entries,
  unique Images and all affected Cels, changed pixel/index counts and bounds, and
  before/after content observations applicable to the branch.
- Delivery requires real-runtime parity across input boundaries, Color Modes,
  Channels, Applications, Selections, Palette Changes, Background and linked targets,
  persisted output, explicit no-op, and failure rollback.

## Consequences

- Agents receive the complete useful native adjustment without hidden editor defaults
  or meaningless channel choices.
- Integer percentage inputs match Aseprite's documented/editor vocabulary and remain
  easy to generate and validate.
- Indexed and Palette behavior reuse the shared accepted contracts instead of being
  disguised as ordinary RGB pixel mutation.
- Future advanced tonal controls require their own Aseprite-native Operations rather
  than silently extending Brightness/Contrast.

## Rejected alternatives

### Accept arbitrary numbers because the internal parameter is a double

That would exceed the documented/editor range and make unsupported extrapolation part
of SPA's public contract.

### Expose Alpha or Index channels

The native Brightness/Contrast implementation does not modify them. Encoding a flag is
not evidence of a supported operation.

### Reject the zero/zero identity

It is a valid native setting and SPA already permits explicit, observable no-op raster
operations.

### Add gamma, curves, or a custom formula

Those are not parameters of Aseprite's Brightness/Contrast Filter. Color Curve remains
a distinct native Filter capability.

### Reimplement the mapping for predictable output

That would create a second semantic authority and could drift from Aseprite's native
rounding, clamping, Palette, and RGB Map behavior.
