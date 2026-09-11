# ADR-0078: Define native Hue/Saturation Filter

## Status

Accepted

## Context

Aseprite exposes Hue/Saturation as a native `FilterWithPalette`. Its official script
documentation describes HSL and HSV modes plus integer Hue, Saturation,
Lightness/Value, and Alpha adjustments. The editor and source additionally expose
`HSV+` and `HSL+`: the native implementation has four modes combining HSL or HSV with
multiplicative or additive Saturation and Lightness/Value adjustment.

The accepted script strings and internal enum include `hsv`, `hsv_mul`, `hsv_add`,
`hsl_add`, and default-to-HSL behavior for other strings. SPA cannot expose the silent
fallback or numeric enum. The additive modes are native editor capabilities, but their
current documentation gap requires direct runtime proof before SPA advertises the
complete command.

Hue is always added and wrapped. Saturation and Lightness/Value follow the selected
multiplicative or additive mode. Alpha uses its own native relative calculation and
does not become additive in a `+` mode. On Grayscale Sprites the implementation uses
only multiplicative HSL Lightness and optional Alpha; Hue, Saturation, and the HSL/HSV
mode do not affect the result.

The shared channel mask can encode Index, but Hue/Saturation has no stored-Index
operation. Color and Alpha calculations are also independently gated by their selected
channels, so a sparse request accepting unrelated values would legitimize ignored
inputs.

## Decision

- `spa filter hue-saturation` is a deterministic Filter Operation that delegates to
  Aseprite's native Hue/Saturation command through one fixed Lua Kernel handler.
- The request uses conditional typed adjustment values rather than one sparse object:
  - `hsl-multiply` and `hsl-add` require integer `hue` in `-180..180`, `saturation`
    in `-100..100`, and `lightness` in `-100..100`.
  - `hsv-multiply` and `hsv-add` require integer `hue` in `-180..180`, `saturation`
    in `-100..100`, and `value` in `-100..100`.
  - `grayscale` requires integer `lightness` in `-100..100` and carries no Hue,
    Saturation, HSL, or HSV choice.
- The RGB and Indexed component forms accept a non-empty subset of `red`, `green`,
  `blue`, and `alpha`. Grayscale accepts a non-empty subset of `gray` and `alpha`.
  The `index` form is invalid.
- When any RGB component is selected, exactly one HSL or HSV adjustment is required.
  That adjustment is forbidden when no RGB component is selected. When `gray` is
  selected, the `grayscale` adjustment is required and is otherwise forbidden.
- Integer `alpha` in `-100..100` is required exactly when the Alpha channel is
  selected and is forbidden otherwise. Aseprite's native behavior preserves fully
  transparent zero Alpha rather than using the adjustment to resurrect it.
- Every explicit adjustment may be zero. A request whose governed values are all zero
  is a valid, observable no-op.
- Map public modes only through the fixed Lua Kernel:
  - `hsl-multiply` to native `hsl`;
  - `hsv-multiply` to native `hsv`;
  - `hsl-add` to native `hsl_add`; and
  - `hsv-add` to native `hsv_add`.
  Unknown modes fail schema validation and never reach Aseprite's fallback.
- Hue/Saturation uses ADR-0076 Filter Application: RGB, Grayscale, and Indexed
  `pixels`; Indexed `indexed-palette-entries`; and RGB `rgb-palette-colors`.
  Grayscale accepts only `pixels`.
- Background Alpha, Filter Cels Target, Selection Application, Palette basis/change,
  Palette Entry, Linked Image, and all-or-nothing rules apply to each valid branch.
- The request accepts no Tiled Mode, direct output color, custom color-space matrix,
  arbitrary transfer function, or stored-Index adjustment.
- Aseprite owns HSL/HSV conversion, Hue wrap, multiply/add behavior, component
  projection, Alpha handling, clamping, integer conversion, Palette exact matching,
  and Indexed RGB Map quantization. Lua and Python do not reproduce this math.
- The Operation Result reports the public mode and adjustment values, effective
  Channels and Filter Application, Palette and target facts, changed Palette Entries,
  unique Images and affected Cels, pixel/index changes and bounds, and persisted
  before/after observations.
- The complete Operation remains absent from a runtime's Surface Manifest until real
  headless tests prove all four color modes, including `hsl-add` and `hsv-add`, through
  the supported public command seam. SPA does not silently ship a two-mode subset or
  map additive requests to multiplicative behavior.

## Consequences

- Agents can request every native editor adjustment mode without ambiguous
  Lightness/Value naming or numeric enums.
- Color, Grayscale, and Alpha fields appear only when they can influence the selected
  channels.
- The current documentation gap becomes a runtime delivery gate instead of either a
  permanent omission or an unsupported promise.
- Indexed and Palette destinations reuse the explicit Filter Application contract.

## Rejected alternatives

### Expose only documented HSL and HSV modes

That would omit the native HSL+ and HSV+ editor capabilities despite source-level
public command mappings. Runtime proof, rather than documentation absence alone,
decides delivery.

### Expose Aseprite's numeric mode enum or fallback strings

Numeric ordering and unknown-string fallback are implementation details and cannot
provide a strict schema.

### Use `lightness` for HSV

HSV adjusts Value, not HSL Lightness. Separate field names preserve Aseprite's color
model vocabulary.

### Accept all color fields on Grayscale

The native implementation ignores Hue, Saturation, and mode there; accepting them
would create false functionality.

### Make Alpha follow additive mode

Aseprite applies Alpha through its own relative multiplication regardless of HSL/HSV
`+` mode. SPA does not redefine it.

### Reimplement color conversion for consistency

That would create a second authority for conversion, clamping, rounding, Palette, and
RGB Map behavior.
